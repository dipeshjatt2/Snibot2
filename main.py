import os
import ssl
import socket
import requests
import subprocess
import asyncio
import sys
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyromod import listen

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
LOGS_CHANNEL = int(os.getenv("LOGS_CHANNEL"))

app = Client("domain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def get_http_status(domain: str) -> str:
    try:
        if not domain.startswith(('http://', 'https://')):
            domain = f"http://{domain}"
        response = requests.get(domain, timeout=10, allow_redirects=False)
        return f"{response.status_code} {response.reason}"
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"

def get_ssl_cert_info(domain: str) -> dict:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
        issuer = dict(x[0] for x in cert['issuer'])
        subject = dict(x[0] for x in cert['subject'])
        return {
            'issuer': issuer.get('organizationName', 'Unknown'),
            'subject': subject.get('commonName', 'Unknown'),
            'valid_from': datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z'),
            'valid_to': datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z'),
            'version': cert.get('version', 'Unknown'),
            'serial_number': cert.get('serialNumber', 'Unknown')
        }
    except Exception as e:
        print(f"SSL Error: {str(e)}")
        return None

async def get_domain_info(domain: str) -> str:
    clean_domain = domain.replace('http://', '').replace('https://', '').split('/')[0]
    try:
        status = get_http_status(clean_domain)
        result = f"🔍 Domain Information for {clean_domain}\n\n"
        result += f"📡 HTTP Status: {status}\n\n"
        ssl_info = get_ssl_cert_info(clean_domain)
        if ssl_info:
            result += "🔐 SSL Certificate Info:\n"
            result += f"  • Issuer: {ssl_info['issuer']}\n"
            result += f"  • Subject: {ssl_info['subject']}\n"
            result += f"  • Valid From: {ssl_info['valid_from']}\n"
            result += f"  • Valid To: {ssl_info['valid_to']}\n"
            result += f"  • Serial: {ssl_info['serial_number']}\n\n"
        else:
            result += "⚠️ Could not retrieve SSL certificate\n\n"
        return result
    except Exception as e:
        return f"⚠️ Error getting domain information: {str(e)}"

async def verify_subfinder_installation():
    try:
        result = subprocess.run(["subfinder", "-version"], capture_output=True, text=True)
        if "subfinder" in result.stdout.lower():
            print("✅ subfinder is installed")
            return True
        possible_paths = [
            os.path.expanduser("~/go/bin/subfinder"),
            "/usr/local/bin/subfinder",
            "/usr/bin/subfinder",
            "/snap/bin/subfinder"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ subfinder found at: {path}")
                dir_path = os.path.dirname(path)
                if dir_path not in os.environ["PATH"]:
                    os.environ["PATH"] += os.pathsep + dir_path
                return True
        return False
    except Exception as e:
        print(f"❌ Verification error: {str(e)}")
        return False

async def install_subfinder():
    try:
        if await verify_subfinder_installation():
            return True
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "golang", "git"], check=True)
        if "GOPATH" not in os.environ:
            os.environ["GOPATH"] = os.path.expanduser("~/go")
            os.environ["PATH"] += os.pathsep + os.path.expanduser("~/go/bin")
        install_cmd = "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
        result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Installation failed: {result.stderr}")
            return False
        return await verify_subfinder_installation()
    except Exception as e:
        print(f"❌ Installation error: {str(e)}")
        return False

async def run_subfinder(input_file: str, output_file: str, progress_msg: Message = None):
    try:
        if not await install_subfinder():
            return False

        with open(input_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
        total_domains = len(domains)
        if total_domains == 0:
            return False

        cmd = ["subfinder", "-dL", input_file]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        found_subdomains = []
        count = 0
        start_time = time.time()
        last_update = start_time

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            sub = line.decode().strip()
            if sub:
                found_subdomains.append(sub)
                count += 1

            now = time.time()
            if progress_msg and now - last_update >= 120:
                minutes = int((now - start_time) // 60)
                await progress_msg.edit_text(
                    f"🔍 Subdomain scan in progress...\n"
                    f"Elapsed Time: {minutes} min\n"
                    f"Total Domains in Input: {total_domains}\n"
                    f"Subdomains Found: {count}"
                )
                last_update = now

        await process.wait()

        with open(output_file, 'w') as f:
            f.write('\n'.join(found_subdomains))

        if progress_msg:
            total_minutes = int((time.time() - start_time) // 60)
            await progress_msg.edit_text(
                f"✅ Subdomain scan completed!\n"
                f"Time Taken: {total_minutes} min\n"
                f"Total Domains in Input: {total_domains}\n"
                f"Total Subdomains Found: {count}"
            )

        return True
    except Exception as e:
        print(f"❌ Subfinder error: {str(e)}")
        return False

async def log_to_channel(client: Client, content: str, document_path: str = None):
    try:
        if not LOGS_CHANNEL:
            return False
        try:
            chat = await client.get_chat(LOGS_CHANNEL)
            if not chat.permissions.can_send_messages:
                print("❌ Bot lacks send permissions in channel")
                return False
        except Exception as e:
            print(f"❌ Channel access error: {str(e)}")
            return False
        if document_path and os.path.exists(document_path):
            await client.send_document(
                chat_id=LOGS_CHANNEL,
                document=document_path,
                caption=content[:1024]
            )
        else:
            await client.send_message(
                chat_id=LOGS_CHANNEL,
                text=content[:4096]
            )
        return True
    except Exception as e:
        print(f"⚠️ Channel logging failed: {str(e)}")
        return False

@app.on_message(filters.command("dominfo"))
async def dominfo_command(client: Client, message: Message):
    domain = " ".join(message.command[1:]).strip()
    if not domain:
        await message.reply("Please provide a domain after /dominfo command.")
        return
    try:
        processing_msg = await message.reply("🔍 Gathering domain information...")
        info = await get_domain_info(domain)
        await processing_msg.edit_text(info[:4000])
        await log_to_channel(
            client,
            f"#DomainScan by {message.from_user.mention}\n"
            f"Query: {domain}\n\n{info}",
            None
        )
    except Exception as e:
        error_msg = f"⚠️ Error scanning domain: {str(e)}"
        await message.reply(error_msg)
        await log_to_channel(client, f"#Error\n{error_msg}", None)

@app.on_message(filters.document)
async def handle_subdomains_file(client: Client, message: Message):
    if not message.document.file_name.lower().endswith('.txt'):
        return
    try:
        progress_msg = await message.reply("🔍 Starting subdomain scan...")
        file_path = await message.download()
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            await progress_msg.edit_text("❌ Invalid file")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        output_file = f"subdomains_{message.id}.txt"
        success = await run_subfinder(file_path, output_file, progress_msg)
        if not success or not os.path.exists(output_file):
            await progress_msg.edit_text("❌ Scan failed or no subdomains found")
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(output_file):
                os.remove(output_file)
            return
        with open(output_file, 'r') as f:
            subdomain_count = len(f.readlines())
        await message.reply_document(
            document=output_file,
            caption=f"✅ Scan complete. Found {subdomain_count} subdomains."
        )
        await log_to_channel(
            client,
            f"#SubdomainScan by {message.from_user.mention}\n"
            f"File: {message.document.file_name}\n"
            f"Found {subdomain_count} subdomains.",
            output_file
        )
        os.remove(file_path)
        os.remove(output_file)
        await progress_msg.delete()
    except Exception as e:
        error_msg = f"⚠️ Error processing file: {str(e)}"
        await message.reply(error_msg)
        await log_to_channel(client, f"#Error\n{error_msg}", None)
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'output_file' in locals() and os.path.exists(output_file):
            os.remove(output_file)
        if 'progress_msg' in locals():
            try:
                await progress_msg.delete()
            except:
                pass

async def main():
    print("🤖 Bot is starting...")
    if not await install_subfinder():
        print("❌ Critical: Subfinder installation failed. Exiting.")
        sys.exit(1)
    print("✅ All requirements verified. Starting bot...")
    await app.start()
    if LOGS_CHANNEL:
        try:
            chat = await app.get_chat(LOGS_CHANNEL)
            print(f"✅ Log channel accessible: {chat.title}")
        except Exception as e:
            print(f"❌ Can't access log channel: {str(e)}")
    print("🤖 Bot is now running!")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
    finally:
        asyncio.get_event_loop().run_until_complete(app.stop())
        print("✅ Bot stopped cleanly")eanly")