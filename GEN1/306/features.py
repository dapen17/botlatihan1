import asyncio
import re
import json
from telethon import events, errors
from telethon.tl.types import InputPeerUser
from datetime import datetime
from collections import defaultdict

# Path file JSON untuk menyimpan data
DATA_FILE = "data.json"

def load_data():
    """Memuat data dari file JSON."""
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "active_groups": {},
            "active_bc_interval": {},
            "blacklist": [],
            "usernames_history": {},
            "message_count": {},
            "auto_replies": {}
        }

def save_data(data):
    """Menyimpan data ke file JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Load data awal
data = load_data()

# Menyimpan status per akun dan grup
active_groups = data["active_groups"]
active_bc_interval = data["active_bc_interval"]
blacklist = set(data["blacklist"])
usernames_history = data["usernames_history"]
message_count = defaultdict(int, data["message_count"])
auto_replies = data["auto_replies"]

def parse_interval(interval_str):
    """Konversi format [10s, 1m, 2h, 1d] menjadi detik."""
    match = re.match(r'^(\d+)([smhd])$', interval_str)
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    return value * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]

def get_today_date():
    """Mengembalikan tanggal hari ini dalam format YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")

async def configure_event_handlers(client, user_id):
    """Konfigurasi semua fitur bot untuk user_id tertentu."""

    # Spam pesan ke grup dengan interval tertentu
    @client.on(events.NewMessage(pattern=r'^306 hastle (.+) (\d+[smhd])$'))
    async def hastle_handler(event):
        custom_message, interval_str = event.pattern_match.groups()
        group_id = event.chat_id
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_groups.get(group_id, {}).get(user_id, False):
            await event.reply("⚠️ Spam sudah berjalan untuk akun Anda di grup ini.")
            return

        active_groups.setdefault(group_id, {})[user_id] = True
        save_data(data)  # Simpan data ke file JSON
        await event.reply(f"✅ Memulai spam: {custom_message} setiap {interval_str} untuk akun Anda.")
        while active_groups[group_id][user_id]:
            try:
                await client.send_message(group_id, custom_message)
                message_count[get_today_date()] += 1
                save_data(data)  # Simpan data ke file JSON
                await asyncio.sleep(interval)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.reply(f"⚠️ Error: {e}")
                active_groups[group_id][user_id] = False
                save_data(data)  # Simpan data ke file JSON

    # Hentikan spam di grup
    @client.on(events.NewMessage(pattern=r'^306 stop$'))
    async def stop_handler(event):
        group_id = event.chat_id
        if active_groups.get(group_id, {}).get(user_id, False):
            active_groups[group_id][user_id] = False
            save_data(data)  # Simpan data ke file JSON
            await event.reply("✅ Spam dihentikan untuk akun Anda di grup ini.")
        else:
            await event.reply("⚠️ Tidak ada spam yang berjalan untuk akun Anda di grup ini.")

    # Tes koneksi bot
    @client.on(events.NewMessage(pattern=r'^306 ping$'))
    async def ping_handler(event):
        await event.reply("🏓 Pong! Bot aktif.")
        message_count[get_today_date()] += 1
        save_data(data)  # Simpan data ke file JSON

    # Broadcast pesan ke semua chat kecuali blacklist
    @client.on(events.NewMessage(pattern=r'^306 bcstar (.+)$'))
    async def broadcast_handler(event):
        custom_message = event.pattern_match.group(1)
        await event.reply(f"✅ Memulai broadcast ke semua chat: {custom_message}")
        async for dialog in client.iter_dialogs():
            if dialog.id in blacklist:
                continue
            try:
                await client.send_message(dialog.id, custom_message)
                message_count[get_today_date()] += 1
                save_data(data)  # Simpan data ke file JSON
            except Exception as e:
                print(f"Gagal mengirim pesan ke {dialog.name}: {e}")

    # Broadcast pesan ke semua chat dengan interval tertentu
    @client.on(events.NewMessage(pattern=r'^306 bcstarw (\d+[smhd]) (.+)$'))
    async def broadcast_with_interval_handler(event):
        interval_str, custom_message = event.pattern_match.groups()
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_bc_interval.get(user_id, {}).get("all", False):
            await event.reply("⚠️ Broadcast interval sudah berjalan.")
            return

        active_bc_interval.setdefault(user_id, {})["all"] = True
        save_data(data)  # Simpan data ke file JSON
        await event.reply(f"✅ Memulai broadcast dengan interval {interval_str}: {custom_message}")
        while active_bc_interval[user_id]["all"]:
            async for dialog in client.iter_dialogs():
                if dialog.id in blacklist:
                    continue
                try:
                    await client.send_message(dialog.id, custom_message)
                    message_count[get_today_date()] += 1
                    save_data(data)  # Simpan data ke file JSON
                except Exception as e:
                    print(f"Gagal mengirim pesan ke {dialog.name}: {e}")
            await asyncio.sleep(interval)

    # Hentikan broadcast interval
    @client.on(events.NewMessage(pattern=r'^306 stopbcstarw$'))
    async def stop_broadcast_interval_handler(event):
        if active_bc_interval.get(user_id, {}).get("all", False):
            active_bc_interval[user_id]["all"] = False
            save_data(data)  # Simpan data ke file JSON
            await event.reply("✅ Broadcast interval dihentikan.")
        else:
            await event.reply("⚠️ Tidak ada broadcast interval yang berjalan.")

    # Broadcast pesan hanya ke grup dengan interval tertentu
    @client.on(events.NewMessage(pattern=r'^306 bcstargr(\d+) (\d+[smhd]) (.+)$'))
    async def broadcast_group_handler(event):
        group_number = event.pattern_match.group(1)
        interval_str, custom_message = event.pattern_match.groups()[1:]
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_bc_interval.get(user_id, {}).get(f"group{group_number}", False):
            await event.reply(f"⚠️ Broadcast ke grup {group_number} sudah berjalan.")
            return

        active_bc_interval.setdefault(user_id, {})[f"group{group_number}"] = True
        save_data(data)  # Simpan data ke file JSON
        await event.reply(f"✅ Memulai broadcast ke grup {group_number} dengan interval {interval_str}: {custom_message}")
        while active_bc_interval[user_id][f"group{group_number}"]:
            async for dialog in client.iter_dialogs():
                if dialog.is_group and dialog.id not in blacklist:
                    try:
                        await client.send_message(dialog.id, custom_message)
                        message_count[get_today_date()] += 1
                        save_data(data)  # Simpan data ke file JSON
                    except Exception as e:
                        print(f"Gagal mengirim pesan ke {dialog.name}: {e}")
            await asyncio.sleep(interval)

    # Hentikan broadcast grup
    @client.on(events.NewMessage(pattern=r'^306 stopbcstargr(\d+)$'))
    async def stop_broadcast_group_handler(event):
        group_number = event.pattern_match.group(1)
        if active_bc_interval.get(user_id, {}).get(f"group{group_number}", False):
            active_bc_interval[user_id][f"group{group_number}"] = False
            save_data(data)  # Simpan data ke file JSON
            await event.reply(f"✅ Broadcast ke grup {group_number} dihentikan.")
        else:
            await event.reply(f"⚠️ Tidak ada broadcast grup {group_number} yang berjalan.")

    # Tambahkan grup/chat ke blacklist
    @client.on(events.NewMessage(pattern=r'^306 bl$'))
    async def blacklist_handler(event):
        chat_id = event.chat_id
        blacklist.add(chat_id)
        save_data(data)  # Simpan data ke file JSON
        await event.reply("✅ Grup ini telah ditambahkan ke blacklist.")

    # Hapus grup/chat dari blacklist
    @client.on(events.NewMessage(pattern=r'^306 unbl$'))
    async def unblacklist_handler(event):
        chat_id = event.chat_id
        if chat_id in blacklist:
            blacklist.remove(chat_id)
            save_data(data)  # Simpan data ke file JSON
            await event.reply("✅ Grup ini telah dihapus dari blacklist.")
        else:
            await event.reply("⚠️ Grup ini tidak ada dalam blacklist.")

    @client.on(events.NewMessage(pattern=r'^306 help$'))
    async def help_handler(event):
        help_text = (
            "📋 **Daftar Perintah yang Tersedia:**\n\n"
            "1. 306 hastle [pesan] [waktu][s/m/h/d]\n"
            "   Spam pesan di grup dengan interval tertentu.\n"
            "2. 306 stop\n"
            "   Hentikan spam di grup.\n"
            "3. 306 ping\n"
            "   Tes koneksi bot.\n"
            "4. 306 bcstar [pesan]\n"
            "   Broadcast ke semua chat kecuali blacklist.\n"
            "5. 306 bcstarw [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast ke semua chat dengan interval tertentu.\n"
            "6. 306 stopbcstarw\n"
            "   Hentikan broadcast interval.\n"
            "7. 306 bcstargr [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast hanya ke grup dengan interval tertentu.\n"
            "8. 306 bcstargr1 [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast hanya ke grup 1 dengan interval tertentu.\n"
            "9. 306 stopbcstargr[1-10]\n"
            "   Hentikan broadcast ke grup tertentu.\n"
            "10. 306 bl\n"
            "    Tambahkan grup/chat ke blacklist.\n"
            "11. 306 unbl\n"
            "    Hapus grup/chat dari blacklist.\n"
            "12. 306 setreply [pesan]\n"
            "    Atur pesan auto-reply.\n"
            "13. 306 stopall\n"
            "    Hentikan semua pengaturan dan reset bot.\n"
        )
        await event.reply(help_text)


    # Atur auto-reply
    @client.on(events.NewMessage(pattern=r'^306 setreply (.+)$'))
    async def set_auto_reply(event):
        reply_message = event.pattern_match.group(1)
        auto_replies[user_id] = reply_message
        save_data(data)  # Simpan data ke file JSON
        await event.reply(f"\u2705 Auto-reply diatur: {reply_message}")

    # Menangani auto-reply
    @client.on(events.NewMessage(incoming=True))
    async def auto_reply_handler(event):
        if event.is_private and user_id in auto_replies and auto_replies[user_id]:
            try:
                sender = await event.get_sender()
                peer = InputPeerUser(sender.id, sender.access_hash)
                await client.send_message(peer, auto_replies[user_id])
                await client.send_read_acknowledge(peer)
                message_count[get_today_date()] += 1
                save_data(data)  # Simpan data ke file JSON
            except errors.rpcerrorlist.UsernameNotOccupiedError:
                print("Gagal mengirim auto-reply: Username tidak ditemukan.")
            except errors.rpcerrorlist.FloodWaitError as e:
                print(f"Bot terkena flood wait. Coba lagi dalam {e.seconds} detik.")
            except Exception as e:
                print(f"Gagal mengirim auto-reply: {e}")

    # Hentikan semua pengaturan
    @client.on(events.NewMessage(pattern=r'^306 stopall$'))
    async def stop_all_handler(event):
        for group_key in active_bc_interval.get(user_id, {}).keys():
            active_bc_interval[user_id][group_key] = False
        auto_replies[user_id] = ""
        blacklist.clear()
        for group_id in active_groups.keys():
            active_groups[group_id][user_id] = False
        save_data(data)  # Simpan data ke file JSON
        await event.reply("\u2705 Semua pengaturan telah direset dan semua broadcast dihentikan.")
