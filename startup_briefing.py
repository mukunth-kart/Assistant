import os
import socket
import asyncio
import subprocess
import datetime

import edge_tts
import openai

try:
    from config import GROQ_API_KEY
    import scheduler
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from config import GROQ_API_KEY
    import scheduler

def is_online():
    """Checks for active internet connection using a fast socket check to DNS."""
    try:
        socket.setdefaulttimeout(3)
        # Attempt to connect to Google Public DNS
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False

def play_mp3_native(mp3_path: str):
    """Plays an MP3 file silently in the background using Windows Media Player COM via PowerShell."""
    abs_path = os.path.abspath(mp3_path)
    ps_script = f"""
    $player = New-Object -ComObject WMPlayer.OCX
    $player.URL = "{abs_path}"
    $player.controls.play()
    
    # Wait until it starts loading or playing (playState changes from 0/Undefined)
    $timeout = 50
    while (($player.playState -eq 0 -or $player.playState -eq 9) -and $timeout -gt 0) {{
        Start-Sleep -m 100
        $timeout--
    }}
    
    # Loop while it is actively playing (3), buffering (6), or waiting (7)
    while ($player.playState -eq 3 -or $player.playState -eq 6 -or $player.playState -eq 7) {{
        Start-Sleep -m 100
    }}
    
    # Explicitly close player to release the file lock
    $player.close()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($player) | Out-Null
    [System.GC]::Collect()
    """
    # 0x08000000 is CREATE_NO_WINDOW to prevent empty console window popups
    subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True, creationflags=0x08000000)

def speak_offline_native(text: str):
    """Speaks text offline using Windows Speech API (SAPI) via PowerShell."""
    # Escape double quotes for PowerShell
    safe_text = text.replace('"', '`"')
    ps_script = f"""
    Add-Type -AssemblyName System.Speech
    $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $speak.Speak("{safe_text}")
    """
    # 0x08000000 is CREATE_NO_WINDOW to prevent empty console window popups
    subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script], capture_output=True, creationflags=0x08000000)

async def generate_edge_tts_briefing(text: str, output_path: str):
    """Generates an MP3 file using Microsoft Edge's free TTS service."""
    communicate = edge_tts.Communicate(text, "en-GB-SoniaNeural")
    await communicate.save(output_path)

def generate_online_script(itinerary: str) -> str:
    """Uses Groq Llama 3 to convert the raw itinerary into a short, conversational briefing script."""
    client = openai.OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    
    system_prompt = (
        "You are a highly efficient, professional personal secretary. "
        "Read the itinerary and generate a short, conversational morning briefing script (max 4 sentences). "
        "Keep it highly motivational and concise. Do not include markdown formatting or emoji descriptions in the text."
    )
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is today's schedule:\n{itinerary}"}
        ]
    )
    return response.choices[0].message.content.strip()

def generate_offline_script_local(day_name: str) -> str:
    """Fallback itinerary generator that constructs a natural speech script offline."""
    import database
    hard_constraints = database.get_hard_constraints(day_name)
    flexible_tasks = database.get_pending_flexible_tasks()
    
    script_parts = [f"Good morning. Here is your offline schedule summary for {day_name}."]
    
    if hard_constraints:
        script_parts.append("You have fixed events today:")
        for hc in hard_constraints:
            script_parts.append(f"{hc['title']} from {hc['start_time']} to {hc['end_time']}.")
            
    if flexible_tasks:
        top_task = flexible_tasks[0]
        script_parts.append(f"Your highest priority task is: {top_task['title']}.")
        script_parts.append(f"You have {len(flexible_tasks)} tasks to complete in total.")
    else:
        script_parts.append("No pending tasks today.")
        
        
    script_parts.append("Have a productive day!")
    return " ".join(script_parts)

def send_telegram_reminder(message: str):
    """Sends a Telegram notification reminder if bot token and user chat ID are set."""
    try:
        import database
        import config
        import urllib.request
        import urllib.parse
        
        token = config.TELEGRAM_BOT_TOKEN
        chat_id = database.get_setting("last_chat_id")
        
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
            print("✉️ Telegram reminder notification sent successfully.")
        else:
            print("ℹ️ Telegram bot token or chat ID not set. Skipping Telegram notification.")
    except Exception as e:
        print(f"⚠️ Failed to send Telegram reminder: {e}")

async def main():
    # Wait for Windows audio services and network connection to initialize on boot
    print("Waiting 7 seconds for Windows audio and network services to initialize...")
    await asyncio.sleep(7)
    
    day_name = datetime.datetime.now().strftime("%A")
    print(f"Loading itinerary for {day_name}...")
    itinerary = scheduler.get_day_itinerary(day_name)
    
    has_backlog = "⚠️ Unscheduled / Backlog Tasks:" in itinerary
    
    # 1. Write and open readable text briefing automatically
    briefing_file = "daily_briefing.txt"
    with open(briefing_file, "w", encoding="utf-8") as f:
        f.write(f"=== DAILY BRIEFING: {day_name.upper()} ===\n\n")
        if has_backlog:
            f.write("⚠️ WARNING: Time allocated is not enough for all tasks today!\n")
            f.write("Some high priority tasks have been placed in the Backlog.\n\n")
        f.write(itinerary)
        f.write("\n\nHave a productive day!\n")
    
    print("\n--- Current Schedule ---")
    print(itinerary)
    print("------------------------\n")
    print(f"💾 Readable text briefing saved to {briefing_file}.")
    
    # Auto-open the text file in default editor (Notepad on Windows)
    try:
        os.startfile(briefing_file)
        print("📄 Opened text briefing on screen.")
    except Exception as e:
        print(f"⚠️ Could not auto-open text briefing: {e}")
        
    # 2. Trigger reminders if time is insufficient
    if has_backlog:
        backlog_details = itinerary.split("⚠️ Unscheduled / Backlog Tasks:")[1].strip()
        reminder_msg = (
            f"⚠️ **PA Time Warning**\n"
            f"Time today is insufficient for all tasks. The following tasks remain in your backlog:\n"
            f"{backlog_details}"
        )
        send_telegram_reminder(reminder_msg)
        
    online = is_online() and bool(GROQ_API_KEY)
    
    if online:
        print("🌍 Device is online. Generating premium briefing via Groq & Edge TTS...")
        try:
            # 1. Generate Conversational Script
            script = generate_online_script(itinerary)
            
            # Inject vocal warning if time is not enough
            if has_backlog:
                script = "Just a heads up, there is not enough time to fit all tasks today. " + script
                
            print(f"Briefing Script:\n\"{script}\"\n")
            
            # 2. Synthesize Speech
            output_file = "briefing.mp3"
            await generate_edge_tts_briefing(script, output_file)
            
            # 3. Play MP3
            print("🔊 Playing briefing...")
            play_mp3_native(output_file)
            print("✅ Briefing complete.")
            return
        except Exception as e:
            print(f"⚠️ Error during online flow: {e}. Falling back to offline flow.")
            
    # Offline Fallback Flow
    print("🔌 Device is offline or API key is missing. Using local TTS fallback...")
    script = generate_offline_script_local(day_name)
    if has_backlog:
        script = "Warning. Time is insufficient for all tasks today. " + script
        
    print(f"Offline Script:\n\"{script}\"\n")
    
    print("🔊 Playing offline briefing...")
    speak_offline_native(script)
    print("✅ Offline Briefing complete.")

if __name__ == "__main__":
    asyncio.run(main())
