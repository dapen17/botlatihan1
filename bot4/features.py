import asyncio
import re
from telethon import events, errors
from datetime import datetime
from collections import defaultdict

# Menyimpan status per akun dan grup
active_groups = defaultdict(lambda: defaultdict(bool))  # {group_id: {user_id: status}}
active_bc_interval = defaultdict(lambda: defaultdict(bool))  # {user_id: {type: status}}
blacklist = set()
usernames_history = defaultdict(list)
message_count = defaultdict(int)  # {tanggal: jumlah_pesan}

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

    @client.on(events.NewMessage(pattern=r'^\\hastle (.+) (\d+[smhd])$'))
    async def hastle_handler(event):
        """Spam pesan ke grup dengan interval."""
        custom_message, interval_str = event.pattern_match.groups()
        group_id = event.chat_id
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_groups[group_id][user_id]:
            await event.reply("⚠️ Spam sudah berjalan untuk akun Anda di grup ini.")
            return

        active_groups[group_id][user_id] = True
        await event.reply(f"✅ Memulai spam: {custom_message} setiap {interval_str} untuk akun Anda.")
        while active_groups[group_id][user_id]:
            try:
                await client.send_message(group_id, custom_message)
                message_count[get_today_date()] += 1
                await asyncio.sleep(interval)
            except errors.FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await event.reply(f"⚠️ Error: {e}")
                active_groups[group_id][user_id] = False

    @client.on(events.NewMessage(pattern=r'^\\stop$'))
    async def stop_handler(event):
        """Hentikan spam untuk akun di grup tertentu."""
        group_id = event.chat_id
        if active_groups[group_id][user_id]:
            active_groups[group_id][user_id] = False
            await event.reply("✅ Spam dihentikan untuk akun Anda di grup ini.")
        else:
            await event.reply("⚠️ Tidak ada spam yang berjalan untuk akun Anda di grup ini.")

    @client.on(events.NewMessage(pattern=r'^\\ping$'))
    async def ping_handler(event):
        """Tes koneksi bot."""
        await event.reply("🏓 Pong! Bot aktif.")
        message_count[get_today_date()] += 1

    @client.on(events.NewMessage(pattern=r'^\\bcstar (.+)$'))
    async def broadcast_handler(event):
        """Broadcast pesan ke semua chat kecuali blacklist."""
        custom_message = event.pattern_match.group(1)
        await event.reply(f"✅ Memulai broadcast ke semua chat: {custom_message}")
        async for dialog in client.iter_dialogs():
            if dialog.id in blacklist:
                continue
            try:
                await client.send_message(dialog.id, custom_message)
                message_count[get_today_date()] += 1
            except Exception as e:
                print(f"Gagal mengirim pesan ke {dialog.name}: {e}")

    @client.on(events.NewMessage(pattern=r'^\\bcstarw (\d+[smhd]) (.+)$'))
    async def broadcast_with_interval_handler(event):
        """Broadcast pesan ke semua chat dengan interval tertentu."""
        interval_str, custom_message = event.pattern_match.groups()
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_bc_interval[user_id]["all"]:
            await event.reply("⚠️ Broadcast interval sudah berjalan.")
            return

        active_bc_interval[user_id]["all"] = True
        await event.reply(f"✅ Memulai broadcast dengan interval {interval_str}: {custom_message}")
        while active_bc_interval[user_id]["all"]:
            async for dialog in client.iter_dialogs():
                if dialog.id in blacklist:
                    continue
                try:
                    await client.send_message(dialog.id, custom_message)
                    message_count[get_today_date()] += 1
                except Exception as e:
                    print(f"Gagal mengirim pesan ke {dialog.name}: {e}")
            await asyncio.sleep(interval)

    @client.on(events.NewMessage(pattern=r'^\\stopbcstarw$'))
    async def stop_broadcast_interval_handler(event):
        """Hentikan broadcast interval."""
        if active_bc_interval[user_id]["all"]:
            active_bc_interval[user_id]["all"] = False
            await event.reply("✅ Broadcast interval dihentikan.")
        else:
            await event.reply("⚠️ Tidak ada broadcast interval yang berjalan.")

    @client.on(events.NewMessage(pattern=r'^\\bcstargr(\d+) (\d+[smhd]) (.+)$'))
    async def broadcast_group_handler(event):
        """Broadcast pesan hanya ke grup dengan interval tertentu."""
        group_number = event.pattern_match.group(1)
        interval_str, custom_message = event.pattern_match.groups()[1:]
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("⚠️ Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_bc_interval[user_id][f"group{group_number}"]:
            await event.reply(f"⚠️ Broadcast ke grup {group_number} sudah berjalan.")
            return

        active_bc_interval[user_id][f"group{group_number}"] = True
        await event.reply(f"✅ Memulai broadcast ke grup {group_number} dengan interval {interval_str}: {custom_message}")
        while active_bc_interval[user_id][f"group{group_number}"]:
            async for dialog in client.iter_dialogs():
                if dialog.is_group and dialog.id not in blacklist:
                    try:
                        await client.send_message(dialog.id, custom_message)
                        message_count[get_today_date()] += 1
                    except Exception as e:
                        print(f"Gagal mengirim pesan ke {dialog.name}: {e}")
            await asyncio.sleep(interval)

    @client.on(events.NewMessage(pattern=r'^\\stopbcstargr(\d+)$'))
    async def stop_broadcast_group_handler(event):
        """Hentikan broadcast grup."""
        group_number = event.pattern_match.group(1)
        if active_bc_interval[user_id][f"group{group_number}"]:
            active_bc_interval[user_id][f"group{group_number}"] = False
            await event.reply(f"✅ Broadcast ke grup {group_number} dihentikan.")
        else:
            await event.reply(f"⚠️ Tidak ada broadcast grup {group_number} yang berjalan.")

    @client.on(events.NewMessage(pattern=r'^\\bl$'))
    async def blacklist_handler(event):
        """Tambahkan grup/chat ke blacklist."""
        chat_id = event.chat_id
        blacklist.add(chat_id)
        await event.reply("✅ Grup ini telah ditambahkan ke blacklist.")

    @client.on(events.NewMessage(pattern=r'^\\unbl$'))
    async def unblacklist_handler(event):
        """Hapus grup/chat dari blacklist."""
        chat_id = event.chat_id
        if chat_id in blacklist:
            blacklist.remove(chat_id)
            await event.reply("✅ Grup ini telah dihapus dari blacklist.")
        else:
            await event.reply("⚠️ Grup ini tidak ada dalam blacklist.")

    @client.on(events.NewMessage(pattern=r'^\\help$'))
    async def help_handler(event):
        """Tampilkan daftar perintah."""
        help_text = (
            "📋 **Daftar Perintah yang Tersedia:**\n\n"
            "1. \\hastle [pesan] [waktu][s/m/h/d]\n"
            "   Spam pesan di grup dengan interval tertentu.\n"
            "2. \\stop\n"
            "   Hentikan spam di grup.\n"
            "3. \\ping\n"
            "   Tes koneksi bot.\n"
            "4. \\bcstar [pesan]\n"
            "   Broadcast ke semua chat kecuali blacklist.\n"
            "5. \\bcstarw [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast ke semua chat dengan interval tertentu.\n"
            "6. \\stopbcstarw\n"
            "   Hentikan broadcast interval.\n"
            "7. \\bcstargr [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast hanya ke grup dengan interval tertentu.\n"
            "8. \\bcstargr1 [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast hanya ke grup 1 dengan interval tertentu.\n"
            "9. \\bcstargr2 [waktu][s/m/h/d] [pesan]\n"
            "   Broadcast hanya ke grup 2 dengan interval tertentu.\n"
            "10. \\bcstargr3 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 3 dengan interval tertentu.\n"
            "11. \\bcstargr4 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 4 dengan interval tertentu.\n"
            "12. \\bcstargr5 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 5 dengan interval tertentu.\n"
            "13. \\bcstargr6 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 6 dengan interval tertentu.\n"
            "14. \\bcstargr7 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 7 dengan interval tertentu.\n"
            "15. \\bcstargr8 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 8 dengan interval tertentu.\n"
            "16. \\bcstargr9 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 9 dengan interval tertentu.\n"
            "17. \\bcstargr10 [waktu][s/m/h/d] [pesan]\n"
            "    Broadcast hanya ke grup 10 dengan interval tertentu.\n"
            "18. \\stopbcstargr[1-10]\n"
            "    Hentikan broadcast ke grup tertentu.\n"
            "19. \\bl\n"
            "    Tambahkan grup/chat ke blacklist.\n"
            "20. \\unbl\n"
            "    Hapus grup/chat dari blacklist.\n"
            "21. \\info\n"
            "    Tampilkan informasi akun Anda.\n"
            "22. \\listusn\n"
            "    Tampilkan riwayat username Anda.\n"
            "23. \\totalmessages\n"
            "    Tampilkan total pesan hari ini."
        )
        await event.reply(help_text)
