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
from concurrent.futures import ThreadPoolExecutor

API_ID = 22118129
API_HASH = "43c66e3314921552d9330a4b05b18800"
BOT_TOKEN = "7252664374:AAEJXobeGTOc0ici3gcW-JXP7CpVC4DCrQQ"
LOGS_CHANNEL = -1002843745742

# Global executor for parallel processing
executor = ThreadPoolExecutor(max_workers=10)

app = Client("domain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Utility functions
def get_ip(domain):
    try:
        return socket.gethostbyname(domain)
    except:
        return None

def ping_host(domain):
    try:
        result = subprocess.run(["ping", "-c", "1", domain], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.split("time=")[-1].split(" ms")[0] + " ms"
    except:
        pass
    return "❌ Unreachable"

def check_port(domain, port):
    try:
        with socket.create_connection((domain, port), timeout=5):
            return True
    except:
        return False

def get_server(domain, use_https=False):
    url = f"https://{domain}" if use_https else f"http://{domain}"
    try:
        res = requests.get(url, timeout=5)
        return res.headers.get('Server', 'Unknown'), res.status_code
    except:
        return "Unknown", "❌"

def get_ssl_cert_info(domain):
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
    except:
        return None

def get_location(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}").json()
        return {
            "country": res.get("country", "Unknown"),
            "region": res.get("regionName", "Unknown"),
            "city": res.get("city", "Unknown"),
            "org": res.get("org", "Unknown")
        }
    except:
        return {}

def basic_payload(domain):
    return (
        "GET / HTTP/1.1\n"
        f"Host: {domain}\n"
        "Connection: Upgrade\n"
        "Upgrade: websocket\n"
        "User-Agent: Mozilla/5.0"
    )

async def get_domain_info(domain):
    domain = domain.strip().replace("http://", "").replace("https://", "").split("/")[0]
    ip = get_ip(domain)
    location = get_location(ip) if ip else {}
    ping = ping_host(domain)
    port_80 = check_port(domain, 80)
    port_443 = check_port(domain, 443)

    server_http, status_http = get_server(domain, False)
    server_https, status_https = get_server(domain, True)

    ssl_info = get_ssl_cert_info(domain)

    result = f"🔍 SNI + Server Analysis + Subdomains\n\n"
    result += f"🌐 Domain: {domain}\n"
    result += f"🆔 IP: {ip or '❌ Not found'}\n"
    result += f"🏷 Hostname: {domain}\n\n"
    result += f"📶 SIM: {location.get('org', '❌ Unknown')}\n"
    result += f"📡 Ping: {ping}\n"
    result += f"🔋 Recharge Support: ⚠️ Unknown\n\n"
    result += f"📍 Location:\n"
    result += f"🏳 Country: {location.get('country', 'Unknown')}\n"
    result += f"🗺 Region: {location.get('region', 'Unknown')}\n"
    result += f"🏙 City: {location.get('city', 'Unknown')}\n\n"
    result += f"🔒 Ports:\n"
    result += f"🌐 Port 80: {'🟢 Open' if port_80 else '🔴 Closed'}\n"
    result += f"🔐 Port 443: {'🟢 Open' if port_443 else '🔴 Closed'}\n"
    result += f"⚔️ Server: ⚪ {server_http}\n"
    result += f"⚔️ Server: ⚪ {server_https}\n\n"
    result += f"📊 Website:\n"
    result += f"🌍 HTTP: {status_http}\n"
    result += f"🔗 HTTPS: {status_https}\n\n"

    if ssl_info:
        result += f"🛡️ SSL Certificate Info\n\n"
        result += f"• Issuer: {ssl_info['issuer']}\n"
        result += f"• Subject: {ssl_info['subject']}\n"
        result += f"• Valid From: {ssl_info['valid_from']}\n"
        result += f"• Valid Until: {ssl_info['valid_to']}\n"
        result += f"• Version: {ssl_info['version']}\n"
        result += f"• Serial Number: {ssl_info['serial_number']}\n\n"

    result += f"🧬 SSH Payload:\n{basic_payload(domain)}\n\n"
    result += f"🛰 Subdomains:\n• *.{domain}\n• {domain}\n\n"
    result += "🤖 Bot by : @Andr0idpie9 "
    return result

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
        await message.reply(f"❌ Error: {e}")

async def verify_subfinder_installation():
    try:
        result = subprocess.run(["subfinder", "-version"], capture_output=True, text=True)
        if "subfinder" in result.stdout.lower():
            return True
        possible_paths = [
            os.path.expanduser("~/go/bin/subfinder"),
            "/usr/local/bin/subfinder",
            "/usr/bin/subfinder",
            "/snap/bin/subfinder"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                os.environ["PATH"] += os.pathsep + os.path.dirname(path)
                return True
        return False
    except:
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
        cmd = "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0 and await verify_subfinder_installation()
    except:
        return False

async def log_to_channel(client: Client, content: str, document_path: str = None):
    try:
        if not LOGS_CHANNEL:
            return False
        if document_path and os.path.exists(document_path):
            await client.send_document(chat_id=LOGS_CHANNEL, document=document_path, caption=content[:1024])
        else:
            await client.send_message(chat_id=LOGS_CHANNEL, text=content[:4096])
        return True
    except:
        return False

async def process_domain(domain, output_file, progress_data):
    """Process a single domain with subfinder and update progress"""
    try:
        cmd = ["subfinder", "-d", domain, "-silent"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        found_subs = []
        async for line in process.stdout:
            sub = line.decode().strip()
            if sub:
                found_subs.append(sub)
                progress_data["found"] += 1
        
        # Write results to temporary file
        if found_subs:
            with open(output_file, 'a') as f:
                f.write('\n'.join(found_subs) + '\n')
        
        progress_data["processed"] += 1
        return True
    except:
        progress_data["processed"] += 1
        return False

async def run_parallel_subfinder(input_file: str, output_file: str, progress_msg: Message = None):
    """Run subfinder in parallel for multiple domains"""
    try:
        if not await install_subfinder():
            return False

        with open(input_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
        
        total_domains = len(domains)
        if total_domains == 0:
            return False

        # Clear output file
        open(output_file, 'w').close()

        # Progress tracking
        progress_data = {
            "processed": 0,
            "found": 0,
            "start_time": time.time(),
            "last_update": time.time()
        }

        # Process domains in parallel
        tasks = []
        for domain in domains:
            task = asyncio.create_task(process_domain(domain, output_file, progress_data))
            tasks.append(task)
        
        # Progress updater
        async def update_progress():
            while progress_data["processed"] < total_domains:
                now = time.time()
                if now - progress_data["last_update"] >= 30:  # Update every 30 seconds
                    elapsed = int(now - progress_data["start_time"])
                    await progress_msg.edit_text(
                        f"⚡ Parallel Subdomain Scan ⚡\n\n"
                        f"⏱ Elapsed Time: {elapsed // 60}m {elapsed % 60}s\n"
                        f"📊 Progress: {progress_data['processed']}/{total_domains} domains\n"
                        f"🔎 Subdomains Found: {progress_data['found']}\n"
                        f"🚀 Speed: {progress_data['found'] / max(1, elapsed):.1f} subs/sec\n\n"
                        f"⚙️ Workers: 10 parallel processes"
                    )
                    progress_data["last_update"] = now
                await asyncio.sleep(5)
        
        progress_task = asyncio.create_task(update_progress())
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        progress_task.cancel()
        
        # Final update
        total_time = int(time.time() - progress_data["start_time"])
        await progress_msg.edit_text(
            f"✅ Parallel Scan Completed!\n\n"
            f"⏱ Time Taken: {total_time // 60}m {total_time % 60}s\n"
            f"🌐 Domains Processed: {total_domains}\n"
            f"🔎 Total Subdomains Found: {progress_data['found']}\n"
            f"⚡ Average Speed: {progress_data['found'] / max(1, total_time):.1f} subs/sec\n\n"
            f"📁 Preparing results file..."
        )

        return True
    except Exception as e:
        print(f"Error in parallel subfinder: {e}")
        return False

@app.on_message(filters.document)
async def handle_subdomains_file(client: Client, message: Message):
    if not message.document.file_name.lower().endswith('.txt'):
        return
    
    progress_msg = await message.reply("⚡ Starting parallel subdomain scan with 10 workers...")
    file_path = await message.download()
    output_file = f"subdomains_{message.id}.txt"
    
    success = await run_parallel_subfinder(file_path, output_file, progress_msg)
    if not success:
        await progress_msg.edit_text("❌ Scan failed or no subdomains found")
        return
    
    # Count results and send final file
    subdomain_count = 0
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            subdomain_count = len(f.readlines())
    
    if subdomain_count > 0:
        await message.reply_document(
            document=output_file,
            caption=f"✅ Scan Complete: {subdomain_count} subdomains found"
        )
        await log_to_channel(
            client, 
            f"#SubdomainScan by {message.from_user.mention}\n"
            f"File: {message.document.file_name}\n"
            f"Subdomains Found: {subdomain_count}", 
            output_file
        )
    
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(output_file):
        os.remove(output_file)
    
    await progress_msg.delete()

async def main():
    print("🤖 Bot is starting...")
    if not await install_subfinder():
        print("❌ Subfinder install failed.")
        sys.exit(1)
    await app.start()
    print("✅ Bot running.")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    finally:
        asyncio.get_event_loop().run_until_complete(app.stop())
