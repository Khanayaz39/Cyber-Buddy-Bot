"""
CyberSec Buddy — Telegram Cybersecurity Education Bot
-----------------------------------------------------
A feature-rich Telegram bot that teaches cybersecurity concepts using
the Google Gemini API (free tier).

Features:
  /start      — Welcome message with overview
  /help       — Full command reference
  /topics     — Interactive topic buttons (inline keyboard)
  /quiz       — Multiple-choice cybersecurity quiz
  /score      — View your quiz score
  /tip        — Random cybersecurity tip
  /cve <ID>   — Look up a CVE vulnerability (NVD API)
  /news       — Latest cybersecurity news headlines
  /checklist  — Personal security best-practices checklist
  /reset      — Clear conversation history
  Any text    — Answered by Gemini, scoped to cybersecurity education
"""

import os
import random
import logging
import html
import asyncio
from datetime import datetime

import aiohttp
import feedparser
from dotenv import load_dotenv
from google import genai
from google.genai import types
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------------------------------------------------------
# 1. SETUP
# ---------------------------------------------------------------

# Load .env file so we can keep secrets out of the code
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable")
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY environment variable")

client = genai.Client(api_key=GEMINI_API_KEY)

# Gemini 3.8 Flash — fast, free-tier eligible, great for educational Q&A.
GEMINI_MODEL = "gemini-3.8-flash"

SYSTEM_PROMPT = """You are CyberSec Buddy, an educational assistant living
inside a Telegram bot. Your ONLY job is to teach people about cybersecurity
concepts in a clear, friendly, beginner-accessible way.

Topics you cover: network security, cryptography basics, phishing and social
engineering awareness, password/authentication best practices, malware
concepts (how they work at a conceptual level, not how to build them),
secure coding principles, common vulnerabilities (OWASP Top 10, at a
conceptual/defensive level), incident response basics, privacy, digital
hygiene, penetration testing concepts, threat modeling, cloud security
basics, IoT security, and cybersecurity career guidance.

Rules:
- Explain concepts clearly, with examples and analogies where helpful.
- Keep answers concise for a chat app: use short paragraphs and bullet
  points, avoid huge walls of text.
- Use emojis sparingly to make the conversation feel friendly.
- If asked for something that would provide real-world attack capability
  (working exploit code, malware code, step-by-step hacking instructions
  against a real target), politely decline and redirect to the *defensive*
  or *conceptual* side of the topic instead.
- If a question is unrelated to cybersecurity, gently steer the
  conversation back to cybersecurity topics.
- Never claim to be human. You're a Telegram bot built for education.
"""

# In-memory Gemini chat sessions — one per Telegram chat
chat_sessions = {}

# In-memory quiz scores — {user_id: {"correct": int, "total": int}}
quiz_scores = {}


def get_chat_session(chat_id):
    """Get this chat's Gemini session, creating one if it doesn't exist yet."""
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
    return chat_sessions[chat_id]


# ---------------------------------------------------------------
# 2. QUIZ DATA
# ---------------------------------------------------------------

QUIZ_QUESTIONS = [
    {
        "question": "🔐 What does 'phishing' typically refer to in cybersecurity?",
        "options": [
            "A type of DDoS attack",
            "Tricking users into revealing sensitive info via fake messages",
            "Encrypting files for ransom",
            "Scanning a network for open ports",
        ],
        "correct": 1,
        "explanation": "Phishing is a social engineering attack where attackers send fraudulent messages (emails, texts, etc.) designed to trick people into revealing passwords, credit card numbers, or other sensitive data.",
    },
    {
        "question": "🛡️ What is the primary purpose of a firewall?",
        "options": [
            "Encrypt data at rest",
            "Monitor and filter network traffic based on rules",
            "Remove malware from infected files",
            "Manage user passwords",
        ],
        "correct": 1,
        "explanation": "A firewall monitors incoming and outgoing network traffic and decides whether to allow or block specific traffic based on a defined set of security rules. Think of it as a security guard at a building entrance.",
    },
    {
        "question": "🔑 What is two-factor authentication (2FA)?",
        "options": [
            "Using two different passwords",
            "Logging in from two devices at once",
            "Requiring two different types of verification to prove identity",
            "Encrypting data twice",
        ],
        "correct": 2,
        "explanation": "2FA requires two different types of verification — something you KNOW (password) + something you HAVE (phone/token) or something you ARE (fingerprint). Even if someone steals your password, they can't log in without the second factor.",
    },
    {
        "question": "💀 What type of malware encrypts your files and demands payment?",
        "options": [
            "Spyware",
            "Adware",
            "Ransomware",
            "Worm",
        ],
        "correct": 2,
        "explanation": "Ransomware encrypts a victim's files and demands a ransom payment (usually in cryptocurrency) to restore access. Notable examples include WannaCry, NotPetya, and LockBit.",
    },
    {
        "question": "🌐 What does HTTPS ensure that HTTP does not?",
        "options": [
            "Faster page loading",
            "Encrypted communication between browser and server",
            "Better search engine rankings",
            "Access to all websites",
        ],
        "correct": 1,
        "explanation": "HTTPS (HTTP Secure) uses TLS/SSL to encrypt the data exchanged between your browser and the web server, preventing eavesdropping and tampering. The padlock icon 🔒 in your browser indicates HTTPS is active.",
    },
    {
        "question": "🕵️ What is a 'zero-day vulnerability'?",
        "options": [
            "A bug that was fixed on day zero",
            "A vulnerability that has been known for zero days (unknown to vendor)",
            "An attack that takes zero days to execute",
            "A software that expires after zero days",
        ],
        "correct": 1,
        "explanation": "A zero-day vulnerability is a security flaw unknown to the software vendor — they've had 'zero days' to fix it. These are especially dangerous because no patch exists when they're discovered or exploited.",
    },
    {
        "question": "📧 Which is the BEST way to verify a suspicious email from your 'bank'?",
        "options": [
            "Click the link and see if it looks real",
            "Reply to the email asking if it's legitimate",
            "Contact your bank directly using their official website/phone number",
            "Forward it to all your contacts for their opinion",
        ],
        "correct": 2,
        "explanation": "Never click links or reply to suspicious emails. Instead, contact the organization directly using contact info from their official website or the back of your card. Phishing emails can perfectly spoof sender addresses.",
    },
    {
        "question": "🔒 What is the recommended minimum password length for strong security?",
        "options": [
            "6 characters",
            "8 characters",
            "12+ characters",
            "4 characters",
        ],
        "correct": 2,
        "explanation": "Security experts recommend at least 12-16 characters. Longer passwords are exponentially harder to crack. A passphrase like 'correct-horse-battery-staple' is both long and memorable!",
    },
    {
        "question": "🌍 What does a VPN primarily do?",
        "options": [
            "Makes your internet faster",
            "Blocks all malware automatically",
            "Creates an encrypted tunnel for your internet traffic",
            "Gives you unlimited storage",
        ],
        "correct": 2,
        "explanation": "A VPN (Virtual Private Network) creates an encrypted tunnel between your device and a VPN server, hiding your traffic from your ISP and making it appear as if you're browsing from a different location.",
    },
    {
        "question": "🐛 What is the OWASP Top 10?",
        "options": [
            "A list of the top 10 antivirus programs",
            "A ranking of the 10 most critical web application security risks",
            "The top 10 cybersecurity companies",
            "A list of 10 programming languages for security",
        ],
        "correct": 1,
        "explanation": "The OWASP Top 10 is a widely-used awareness document listing the 10 most critical web application security risks. It's updated regularly and includes risks like Injection, Broken Authentication, and Cross-Site Scripting (XSS).",
    },
    {
        "question": "🎭 What is 'social engineering' in cybersecurity?",
        "options": [
            "Building social media platforms",
            "Manipulating people into breaking security procedures",
            "Engineering social networks",
            "Programming chatbots",
        ],
        "correct": 1,
        "explanation": "Social engineering is the art of manipulating people into giving up confidential information or taking actions that compromise security. It exploits human psychology rather than technical vulnerabilities.",
    },
    {
        "question": "🗄️ What is SQL injection?",
        "options": [
            "Injecting SQL databases into a server",
            "A backup technique for databases",
            "Inserting malicious SQL code through user input to manipulate a database",
            "A method to speed up database queries",
        ],
        "correct": 2,
        "explanation": "SQL injection occurs when an attacker inserts malicious SQL code into input fields (like login forms) that are improperly validated, allowing them to read, modify, or delete database data. It's been in the OWASP Top 10 for years.",
    },
    {
        "question": "📱 What is the safest practice for public Wi-Fi?",
        "options": [
            "Use it freely — it's provided for convenience",
            "Only check email on public Wi-Fi",
            "Avoid sensitive transactions; use a VPN if you must connect",
            "Turn off your device's firewall for better speed",
        ],
        "correct": 2,
        "explanation": "Public Wi-Fi is inherently risky because attackers can eavesdrop on unencrypted traffic or set up fake hotspots. Use a VPN, avoid accessing bank accounts or entering passwords, and prefer mobile data for sensitive tasks.",
    },
    {
        "question": "🔄 Why are software updates important for security?",
        "options": [
            "They add new features only",
            "They make your device look newer",
            "They patch known vulnerabilities that attackers can exploit",
            "They are not important for security",
        ],
        "correct": 2,
        "explanation": "Software updates frequently include patches for known security vulnerabilities. Delaying updates leaves your system exposed to attacks that exploit these known flaws. Enable automatic updates whenever possible!",
    },
    {
        "question": "🏗️ What is the principle of 'least privilege'?",
        "options": [
            "Give everyone admin access for convenience",
            "Users should only have the minimum access needed for their role",
            "Remove all permissions from all users",
            "Privilege is determined by seniority",
        ],
        "correct": 1,
        "explanation": "The principle of least privilege means giving users only the minimum permissions they need to do their job — nothing more. This limits the damage if an account is compromised and reduces the attack surface.",
    },
    {
        "question": "🕸️ What is a DDoS attack?",
        "options": [
            "Direct Data over Secure Sockets",
            "Overwhelming a target with massive traffic to make it unavailable",
            "A type of encryption algorithm",
            "A database management technique",
        ],
        "correct": 1,
        "explanation": "A Distributed Denial of Service (DDoS) attack floods a target (website/server) with so much traffic from many sources that it becomes slow or completely unavailable to legitimate users.",
    },
    {
        "question": "🕵️‍♂️ What is a Man-in-the-Middle (MITM) attack?",
        "options": [
            "A firewall configuration error",
            "An attacker secretly intercepts and possibly alters communication between two parties",
            "A type of brute-force password attack",
            "A method to physically access a server room",
        ],
        "correct": 1,
        "explanation": "In a MITM attack, the attacker secretly positions themselves between two communicating parties (e.g., you and a website), intercepting or even modifying the data in transit. Using HTTPS and avoiding public Wi-Fi without a VPN are key defenses against MITM attacks.",
    },
]

# ---------------------------------------------------------------
# 3. CYBERSECURITY TIPS
# ---------------------------------------------------------------

CYBER_TIPS = [
    "🔑 Use a **password manager** (like Bitwarden or KeePass) to generate and store unique passwords for every account. Reusing passwords is one of the biggest security risks!",
    "📱 Enable **two-factor authentication (2FA)** on all important accounts — email, banking, social media. An authenticator app (like Google Authenticator) is more secure than SMS.",
    "🎣 **Think before you click!** Hover over links to preview URLs before clicking. Phishing links often look similar to real ones but have subtle misspellings (e.g., `g00gle.com`).",
    "🔄 **Keep your software updated!** Enable automatic updates for your OS, browser, and apps. Updates patch security vulnerabilities that attackers actively exploit.",
    "📶 **Avoid sensitive activities on public Wi-Fi.** If you must use public Wi-Fi, use a VPN. Never access banking or enter passwords on open networks.",
    "💾 Follow the **3-2-1 backup rule**: keep 3 copies of important data, on 2 different types of storage, with 1 copy stored offsite (cloud or external drive at another location).",
    "🔒 **Check for HTTPS** (padlock icon) before entering sensitive information on websites. No padlock = your data travels unencrypted and can be intercepted.",
    "🗑️ **Be careful what you share on social media.** Attackers use personal details (pet names, birthdays, schools) to guess security questions or craft targeted phishing attacks.",
    "📧 **Verify unexpected requests** for money, credentials, or sensitive data — even if they appear to come from your boss, bank, or a friend. Call them directly to confirm.",
    "🖥️ **Lock your screen** when stepping away from your computer. Windows: `Win+L`. Mac: `Ctrl+Cmd+Q`. It takes seconds and prevents unauthorized access.",
    "🧹 **Review your app permissions** regularly. Many apps request access to contacts, camera, or location that they don't actually need. Revoke unnecessary permissions.",
    "📨 **Don't open unexpected email attachments**, especially `.exe`, `.zip`, or `.docm` files. Even if the sender looks familiar — their account may be compromised.",
    "🌐 **Use a DNS-level blocker** like NextDNS, Cloudflare's 1.1.1.1 for Families, or Pi-hole to block malicious domains and ads that could serve malware.",
    "🔐 **Encrypt your devices.** Enable BitLocker (Windows), FileVault (Mac), or full-disk encryption on your phone. If your device is stolen, your data stays protected.",
    "🎭 **Be skeptical of urgency.** Scammers create a sense of urgency ('Your account will be locked in 24 hours!') to make you act without thinking. Legitimate companies don't pressure you this way.",
    "🛡️ **Use a standard (non-admin) account** for daily tasks. Only use an admin account when installing software. This limits what malware can do if you accidentally run it.",
    "📲 **Only install apps from official stores** (Google Play, App Store). Side-loaded apps bypass security reviews and are a common malware vector.",
    "🔍 **Google yourself** periodically. Search your name, email, and phone number to see what personal data is publicly exposed. Use services like HaveIBeenPwned.com to check for breaches.",
    "🏠 **Secure your home router**: change the default admin password, use WPA3 (or at least WPA2), disable WPS, and update the firmware regularly.",
    "💡 **Learn to recognize pretexting.** Attackers may impersonate IT support, delivery services, or coworkers to extract information. Always verify identity through a separate channel.",
]

# ---------------------------------------------------------------
# 4. SECURITY CHECKLIST
# ---------------------------------------------------------------

SECURITY_CHECKLIST = """
🛡️ <b>Personal Cybersecurity Checklist</b>

<b>🔑 Passwords &amp; Authentication</b>
☐ Use a password manager for all accounts
☐ Enable 2FA on email, banking, and social media
☐ Use unique passwords for every account (12+ characters)
☐ Never reuse passwords across sites

<b>📱 Devices</b>
☐ Enable automatic OS and app updates
☐ Enable full-disk encryption (BitLocker/FileVault)
☐ Set a strong lock screen PIN/password/biometric
☐ Install apps only from official app stores

<b>🌐 Network &amp; Browsing</b>
☐ Secure home Wi-Fi with WPA3/WPA2 + strong password
☐ Change default router admin credentials
☐ Use a VPN on public Wi-Fi
☐ Check for HTTPS before entering sensitive data

<b>📧 Email &amp; Communication</b>
☐ Don't click links in unexpected emails
☐ Verify sender identity before sharing sensitive info
☐ Be wary of urgent or threatening messages
☐ Don't open unexpected attachments

<b>💾 Data &amp; Privacy</b>
☐ Follow the 3-2-1 backup rule
☐ Review app permissions regularly
☐ Check HaveIBeenPwned.com for breached accounts
☐ Limit personal info shared on social media

<b>🖥️ Good Habits</b>
☐ Lock your screen when stepping away (Win+L / Ctrl+Cmd+Q)
☐ Use a standard (non-admin) account for daily tasks
☐ Keep antivirus/endpoint protection active
☐ Stay informed about current threats

✅ <i>Tip: Screenshot this and check items off as you complete them!</i>
"""

# ---------------------------------------------------------------
# 5. TOPIC DETAILS (for inline keyboard callbacks)
# ---------------------------------------------------------------

TOPIC_DETAILS = {
    "topic_phishing": (
        "🎣 <b>Phishing &amp; Social Engineering</b>\n\n"
        "Phishing is a cyberattack where criminals send fake messages (emails, "
        "texts, calls) pretending to be trusted entities to steal passwords, "
        "credit card numbers, or personal data.\n\n"
        "<b>How to spot it:</b>\n"
        "• Urgent/threatening language ('Account suspended!')\n"
        "• Suspicious sender address (look closely!)\n"
        "• Links that don't match the claimed organization\n"
        "• Requests for sensitive info via email/text\n"
        "• Generic greetings ('Dear Customer')\n\n"
        "💡 <i>When in doubt, contact the organization directly using their official website.</i>"
    ),
    "topic_crypto": (
        "🔐 <b>Cryptography Basics</b>\n\n"
        "Cryptography is the practice of securing communication so only intended "
        "recipients can read it.\n\n"
        "<b>Key concepts:</b>\n"
        "• <b>Symmetric encryption</b>: Same key to encrypt &amp; decrypt (AES)\n"
        "• <b>Asymmetric encryption</b>: Public key encrypts, private key decrypts (RSA)\n"
        "• <b>Hashing</b>: One-way function that creates a fingerprint (SHA-256)\n"
        "• <b>Digital signatures</b>: Proves a message wasn't tampered with\n\n"
        "🔒 <i>HTTPS uses a combination of these to keep your browsing secure!</i>"
    ),
    "topic_firewall": (
        "🧱 <b>Firewalls</b>\n\n"
        "A firewall monitors and controls network traffic based on security rules — "
        "like a security guard for your network.\n\n"
        "<b>Types:</b>\n"
        "• <b>Packet-filtering</b>: Checks packet headers (IP, port)\n"
        "• <b>Stateful</b>: Tracks connection states\n"
        "• <b>Application-layer (WAF)</b>: Inspects application data\n"
        "• <b>Next-gen (NGFW)</b>: Combines all + threat intelligence\n\n"
        "🛡️ <i>Most operating systems have a built-in firewall — make sure yours is enabled!</i>"
    ),
    "topic_owasp": (
        "🐛 <b>OWASP Top 10</b>\n\n"
        "The OWASP Top 10 is the most recognized list of critical web app security risks:\n\n"
        "1. <b>Broken Access Control</b>\n"
        "2. <b>Cryptographic Failures</b>\n"
        "3. <b>Injection</b> (SQL, XSS, etc.)\n"
        "4. <b>Insecure Design</b>\n"
        "5. <b>Security Misconfiguration</b>\n"
        "6. <b>Vulnerable Components</b>\n"
        "7. <b>Auth &amp; Identity Failures</b>\n"
        "8. <b>Data Integrity Failures</b>\n"
        "9. <b>Logging &amp; Monitoring Failures</b>\n"
        "10. <b>SSRF</b> (Server-Side Request Forgery)\n\n"
        "📚 <i>Learn more at owasp.org/Top10</i>"
    ),
    "topic_passwords": (
        "🔑 <b>Password Best Practices</b>\n\n"
        "<b>Do:</b>\n"
        "✅ Use 12+ character passwords or passphrases\n"
        "✅ Use a password manager (Bitwarden, KeePass)\n"
        "✅ Use unique passwords for every account\n"
        "✅ Enable 2FA wherever possible\n\n"
        "<b>Don't:</b>\n"
        "❌ Reuse passwords across sites\n"
        "❌ Use personal info (birthday, pet names)\n"
        "❌ Use common patterns (Password123!)\n"
        "❌ Share passwords via email/text\n\n"
        "💡 <i>A passphrase like 'purple-elephant-dances-quietly' is strong AND memorable!</i>"
    ),
    "topic_2fa": (
        "📱 <b>Two-Factor Authentication (2FA)</b>\n\n"
        "2FA requires two different verification types to prove your identity:\n\n"
        "• <b>Something you know</b>: Password\n"
        "• <b>Something you have</b>: Phone, security key\n"
        "• <b>Something you are</b>: Fingerprint, face\n\n"
        "<b>2FA methods (best → worst):</b>\n"
        "🥇 Hardware security key (YubiKey)\n"
        "🥈 Authenticator app (Google Auth, Authy)\n"
        "🥉 SMS codes (better than nothing, but can be intercepted)\n\n"
        "🔐 <i>Even if your password is stolen, 2FA keeps your account safe!</i>"
    ),
    "topic_ransomware": (
        "💀 <b>Ransomware</b>\n\n"
        "Ransomware encrypts your files and demands payment for the decryption key.\n\n"
        "<b>How it spreads:</b>\n"
        "• Phishing emails with malicious attachments\n"
        "• Exploiting unpatched vulnerabilities\n"
        "• Compromised websites (drive-by downloads)\n"
        "• RDP brute-force attacks\n\n"
        "<b>Protection:</b>\n"
        "🛡️ Regular offline backups (3-2-1 rule)\n"
        "🛡️ Keep systems patched and updated\n"
        "🛡️ Email filtering and awareness training\n"
        "🛡️ Principle of least privilege\n\n"
        "⚠️ <i>Law enforcement recommends NOT paying ransoms — it funds more attacks.</i>"
    ),
    "topic_zeroday": (
        "🕵️ <b>Zero-Day Vulnerabilities</b>\n\n"
        "A zero-day is a security flaw unknown to the vendor — they've had 'zero days' "
        "to fix it.\n\n"
        "<b>Timeline:</b>\n"
        "1. Vulnerability exists in software (unknown)\n"
        "2. Attacker discovers it → zero-day vulnerability\n"
        "3. Attacker creates exploit → zero-day exploit\n"
        "4. Vendor learns about it → race to patch\n"
        "5. Patch released → no longer zero-day\n\n"
        "<b>Defense:</b>\n"
        "• Defense in depth (multiple security layers)\n"
        "• Behavior-based detection (EDR tools)\n"
        "• Network segmentation\n"
        "• Rapid patching processes\n\n"
        "🔍 <i>Famous zero-days: Stuxnet, Log4Shell, EternalBlue</i>"
    ),
    "topic_vpn": (
        "🌐 <b>VPN (Virtual Private Network)</b>\n\n"
        "A VPN creates an encrypted tunnel between your device and a server, "
        "hiding your traffic from your ISP and local network.\n\n"
        "<b>What a VPN does:</b>\n"
        "✅ Encrypts your internet traffic\n"
        "✅ Hides your IP address\n"
        "✅ Protects you on public Wi-Fi\n"
        "✅ Can bypass geo-restrictions\n\n"
        "<b>What a VPN does NOT do:</b>\n"
        "❌ Make you completely anonymous\n"
        "❌ Protect against malware or phishing\n"
        "❌ Replace antivirus software\n\n"
        "💡 <i>Choose a reputable, audited VPN provider. Free VPNs often sell your data!</i>"
    ),
    "topic_soceng": (
        "🎭 <b>Social Engineering</b>\n\n"
        "Social engineering manipulates people into breaking security procedures. "
        "It targets human psychology, not technology.\n\n"
        "<b>Common techniques:</b>\n"
        "• <b>Phishing</b>: Fake emails/messages\n"
        "• <b>Pretexting</b>: Creating a fake scenario\n"
        "• <b>Baiting</b>: Leaving infected USB drives\n"
        "• <b>Tailgating</b>: Following someone through a secure door\n"
        "• <b>Quid pro quo</b>: Offering something in exchange\n"
        "• <b>Vishing</b>: Phone-based phishing\n\n"
        "🧠 <i>The best defense is awareness and verification — always verify through a separate channel!</i>"
    ),
}

# ---------------------------------------------------------------
# 6. TELEGRAM COMMAND HANDLERS
# ---------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message when users first interact with the bot."""
    welcome_text = (
        "👋 <b>Welcome to CyberSec Buddy!</b>\n\n"
        "I'm your personal cybersecurity education assistant, "
        "powered by AI. I can help you learn about:\n\n"
        "🔐 Cryptography &amp; Encryption\n"
        "🎣 Phishing &amp; Social Engineering\n"
        "🔑 Passwords &amp; Authentication\n"
        "💀 Malware &amp; Ransomware\n"
        "🛡️ Network Security &amp; Firewalls\n"
        "🐛 Vulnerabilities (OWASP Top 10)\n"
        "🌐 Privacy &amp; Digital Hygiene\n"
        "🕵️ Threat Intelligence &amp; More!\n\n"
        "<b>🚀 Quick Start:</b>\n"
        "• Just type any cybersecurity question!\n"
        "• Use /topics for interactive topic explorer\n"
        "• Use /quiz to test your knowledge\n"
        "• Use /help for all commands\n\n"
        "⚡ <i>Let's learn cybersecurity together!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display all available commands with descriptions."""
    help_text = (
        "📖 <b>CyberSec Buddy — Command Reference</b>\n\n"
        "🤖 <b>AI Chat</b>\n"
        "Just type any cybersecurity question and I'll answer!\n\n"
        "📚 <b>Learn</b>\n"
        "/topics — Interactive topic explorer with details\n"
        "/tip — Get a random cybersecurity tip\n"
        "/checklist — Personal security best-practices checklist\n\n"
        "🧠 <b>Quiz</b>\n"
        "/quiz — Take a cybersecurity quiz question\n"
        "/score — View your quiz score\n\n"
        "🔍 <b>Research</b>\n"
        "/cve <code>&lt;CVE-ID&gt;</code> — Look up a vulnerability (e.g. /cve CVE-2024-3094)\n"
        "/news — Latest cybersecurity news headlines\n\n"
        "⚙️ <b>Utility</b>\n"
        "/reset — Clear our conversation history\n"
        "/help — Show this help message\n"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")


async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show interactive topic buttons using inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🎣 Phishing", callback_data="topic_phishing"),
            InlineKeyboardButton("🔐 Cryptography", callback_data="topic_crypto"),
        ],
        [
            InlineKeyboardButton("🧱 Firewalls", callback_data="topic_firewall"),
            InlineKeyboardButton("🐛 OWASP Top 10", callback_data="topic_owasp"),
        ],
        [
            InlineKeyboardButton("🔑 Passwords", callback_data="topic_passwords"),
            InlineKeyboardButton("📱 2FA", callback_data="topic_2fa"),
        ],
        [
            InlineKeyboardButton("💀 Ransomware", callback_data="topic_ransomware"),
            InlineKeyboardButton("🕵️ Zero-Days", callback_data="topic_zeroday"),
        ],
        [
            InlineKeyboardButton("🌐 VPN", callback_data="topic_vpn"),
            InlineKeyboardButton("🎭 Social Eng.", callback_data="topic_soceng"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 <b>Cybersecurity Topics</b>\n\nTap a topic to learn more:",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )


async def topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses for topics."""
    query = update.callback_query
    await query.answer()

    topic_key = query.data
    if topic_key in TOPIC_DETAILS:
        await query.edit_message_text(
            text=TOPIC_DETAILS[topic_key],
            parse_mode="HTML",
        )


# ---------------------------------------------------------------
# 7. QUIZ HANDLERS
# ---------------------------------------------------------------

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a random quiz question with inline keyboard answer buttons."""
    question_data = random.choice(QUIZ_QUESTIONS)
    question_index = QUIZ_QUESTIONS.index(question_data)

    keyboard = []
    for i, option in enumerate(question_data["options"]):
        callback_data = f"quiz_{question_index}_{i}"
        keyboard.append([InlineKeyboardButton(option, callback_data=callback_data)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🧠 <b>Cybersecurity Quiz</b>\n\n{question_data['question']}",
        reply_markup=reply_markup,
        parse_mode="HTML",
    )


async def quiz_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quiz answer button presses."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: quiz_{question_index}_{answer_index}
    parts = query.data.split("_")
    question_index = int(parts[1])
    answer_index = int(parts[2])

    question_data = QUIZ_QUESTIONS[question_index]
    correct_index = question_data["correct"]
    user_id = query.from_user.id

    # Initialize score tracking for this user
    if user_id not in quiz_scores:
        quiz_scores[user_id] = {"correct": 0, "total": 0}

    quiz_scores[user_id]["total"] += 1

    if answer_index == correct_index:
        quiz_scores[user_id]["correct"] += 1
        result = "✅ <b>Correct!</b> Great job! 🎉\n\n"
    else:
        correct_answer = question_data["options"][correct_index]
        result = f"❌ <b>Incorrect.</b> The correct answer was:\n<i>{html.escape(correct_answer)}</i>\n\n"

    result += f"📝 {question_data['explanation']}\n\n"

    score = quiz_scores[user_id]
    percentage = (score["correct"] / score["total"]) * 100 if score["total"] > 0 else 0
    result += f"📊 Your score: {score['correct']}/{score['total']} ({percentage:.0f}%)\n\n"
    result += "Use /quiz for another question!"

    await query.edit_message_text(text=result, parse_mode="HTML")


async def score_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the user's quiz score."""
    user_id = update.effective_user.id

    if user_id not in quiz_scores or quiz_scores[user_id]["total"] == 0:
        await update.message.reply_text(
            "📊 You haven't taken any quizzes yet!\n\n"
            "Use /quiz to start testing your cybersecurity knowledge.",
            parse_mode="HTML",
        )
        return

    score = quiz_scores[user_id]
    percentage = (score["correct"] / score["total"]) * 100

    if percentage >= 80:
        grade = "🏆 Excellent!"
        badge = "🌟 Cyber Expert"
    elif percentage >= 60:
        grade = "👍 Good job!"
        badge = "🛡️ Cyber Defender"
    elif percentage >= 40:
        grade = "📚 Keep learning!"
        badge = "📖 Cyber Student"
    else:
        grade = "💪 Don't give up!"
        badge = "🌱 Cyber Beginner"

    score_text = (
        f"📊 <b>Your Quiz Score</b>\n\n"
        f"✅ Correct: {score['correct']}\n"
        f"❌ Incorrect: {score['total'] - score['correct']}\n"
        f"📝 Total questions: {score['total']}\n"
        f"📈 Accuracy: {percentage:.0f}%\n\n"
        f"{grade}\n"
        f"🎖️ Badge: {badge}\n\n"
        f"Use /quiz to keep testing your knowledge!"
    )
    await update.message.reply_text(score_text, parse_mode="HTML")


# ---------------------------------------------------------------
# 8. TIP COMMAND
# ---------------------------------------------------------------

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a random cybersecurity tip."""
    tip = random.choice(CYBER_TIPS)
    tip_text = (
        f"💡 <b>Cybersecurity Tip of the Moment</b>\n\n"
        f"{tip}\n\n"
        f"<i>Use /tip for another tip!</i>"
    )
    # Convert markdown bold to HTML bold for the tip text
    tip_text = tip_text.replace("**", "")  # Remove any stray markdown bold
    await update.message.reply_text(tip_text, parse_mode="HTML")


# ---------------------------------------------------------------
# 9. CVE LOOKUP
# ---------------------------------------------------------------

async def cve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Look up a CVE vulnerability from the National Vulnerability Database."""
    if not context.args:
        await update.message.reply_text(
            "🔍 <b>CVE Lookup</b>\n\n"
            "Usage: <code>/cve CVE-2024-3094</code>\n\n"
            "Looks up vulnerability details from the National Vulnerability Database (NVD).\n\n"
            "<b>Examples:</b>\n"
            "• <code>/cve CVE-2024-3094</code> (XZ Utils backdoor)\n"
            "• <code>/cve CVE-2021-44228</code> (Log4Shell)\n"
            "• <code>/cve CVE-2017-0144</code> (EternalBlue)\n"
            "• <code>/cve CVE-2014-0160</code> (Heartbleed)",
            parse_mode="HTML",
        )
        return

    cve_id = context.args[0].upper()

    # Validate CVE format
    if not cve_id.startswith("CVE-"):
        cve_id = f"CVE-{cve_id}"

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    await update.message.reply_text(
                        f"⚠️ Could not fetch data for <code>{html.escape(cve_id)}</code>. "
                        f"Please check the CVE ID and try again.",
                        parse_mode="HTML",
                    )
                    return

                data = await resp.json()

        if not data.get("vulnerabilities"):
            await update.message.reply_text(
                f"🔍 No results found for <code>{html.escape(cve_id)}</code>.\n\n"
                f"Make sure the format is correct: <code>CVE-YYYY-NNNNN</code>",
                parse_mode="HTML",
            )
            return

        cve_data = data["vulnerabilities"][0]["cve"]
        cve_id_result = cve_data.get("id", "N/A")

        # Get description
        descriptions = cve_data.get("descriptions", [])
        description = "No description available."
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", description)
                break

        # Truncate long descriptions
        if len(description) > 800:
            description = description[:800] + "..."

        # Get CVSS score and severity
        severity = "N/A"
        score = "N/A"
        metrics = cve_data.get("metrics", {})

        # Try CVSS v3.1 first, then v3.0, then v2.0
        for cvss_version in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
            if cvss_version in metrics:
                cvss_data = metrics[cvss_version][0]
                if "cvssData" in cvss_data:
                    score = cvss_data["cvssData"].get("baseScore", "N/A")
                    severity = cvss_data["cvssData"].get("baseSeverity", "N/A")
                elif "baseSeverity" in cvss_data:
                    severity = cvss_data["baseSeverity"]
                break

        # Severity emoji
        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🟢",
        }.get(str(severity).upper(), "⚪")

        # Published date
        published = cve_data.get("published", "N/A")
        if published != "N/A":
            try:
                pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                published = pub_date.strftime("%B %d, %Y")
            except (ValueError, AttributeError):
                pass

        reply = (
            f"🔍 <b>CVE Vulnerability Report</b>\n\n"
            f"🆔 <b>ID:</b> <code>{html.escape(cve_id_result)}</code>\n"
            f"{severity_emoji} <b>Severity:</b> {html.escape(str(severity))}\n"
            f"📊 <b>CVSS Score:</b> {html.escape(str(score))}/10\n"
            f"📅 <b>Published:</b> {html.escape(str(published))}\n\n"
            f"📝 <b>Description:</b>\n{html.escape(description)}\n\n"
            f"🔗 <a href='https://nvd.nist.gov/vuln/detail/{html.escape(cve_id_result)}'>View full details on NVD</a>"
        )

        await update.message.reply_text(reply, parse_mode="HTML", disable_web_page_preview=True)

    except asyncio.TimeoutError:
        await update.message.reply_text(
            "⏱️ The request timed out. The NVD API might be slow — try again in a moment.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"CVE lookup error: {e}")
        await update.message.reply_text(
            "⚠️ Something went wrong while looking up that CVE. Please try again later.",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------
# 10. NEWS COMMAND
# ---------------------------------------------------------------

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch latest cybersecurity news from The Hacker News RSS feed."""
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    rss_url = "https://feeds.feedburner.com/TheHackersNews"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    await update.message.reply_text(
                        "⚠️ Couldn't fetch news right now. Please try again later.",
                        parse_mode="HTML",
                    )
                    return
                rss_content = await resp.text()

        feed = feedparser.parse(rss_content)

        if not feed.entries:
            await update.message.reply_text(
                "📰 No news articles found. Try again later!",
                parse_mode="HTML",
            )
            return

        news_text = "📰 <b>Latest Cybersecurity News</b>\n"
        news_text += "<i>Source: The Hacker News</i>\n\n"

        for i, entry in enumerate(feed.entries[:7], 1):
            title = html.escape(entry.get("title", "No title"))
            link = entry.get("link", "#")
            published = entry.get("published", "")

            # Parse date if available
            date_str = ""
            if published:
                try:
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(published)
                    date_str = f" • {pub_date.strftime('%b %d')}"
                except Exception:
                    pass

            news_text += f"{i}. <a href='{link}'>{title}</a>{date_str}\n\n"

        news_text += "🔄 <i>Use /news to refresh</i>"

        await update.message.reply_text(
            news_text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    except asyncio.TimeoutError:
        await update.message.reply_text(
            "⏱️ The request timed out. Try again in a moment.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"News fetch error: {e}")
        await update.message.reply_text(
            "⚠️ Something went wrong fetching the news. Please try again later.",
            parse_mode="HTML",
        )


# ---------------------------------------------------------------
# 11. CHECKLIST COMMAND
# ---------------------------------------------------------------

async def checklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the personal cybersecurity checklist."""
    await update.message.reply_text(SECURITY_CHECKLIST, parse_mode="HTML")


# ---------------------------------------------------------------
# 12. RESET COMMAND
# ---------------------------------------------------------------

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear the conversation history for this chat."""
    chat_id = update.effective_chat.id
    chat_sessions.pop(chat_id, None)
    await update.message.reply_text(
        "🔄 Conversation history cleared! Send me a new question anytime.",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------
# 13. MESSAGE HANDLER (Gemini AI chat)
# ---------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forward user messages to Gemini and send the response back."""
    chat_id = update.effective_chat.id
    user_message = update.message.text

    # Show "typing..." while we wait for Gemini
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    session = get_chat_session(chat_id)

    try:
        # Run the synchronous Gemini call in a thread to avoid
        # blocking the async event loop
        response = await asyncio.to_thread(session.send_message, user_message)
        reply_text = response.text
    except Exception as e:
        logger.error(f"Gemini API error ({type(e).__name__}): {e}")
        reply_text = (
            "⚠️ Sorry, I ran into an error answering that. Please try again "
            "in a moment. (If this keeps happening, you may have hit the "
            "free tier's rate limit — just wait a minute and try again.)"
        )
        await update.message.reply_text(reply_text)
        return

    # Telegram messages have a ~4096 character limit; split if needed
    for i in range(0, len(reply_text), 4000):
        chunk = reply_text[i : i + 4000]
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # If Markdown parsing fails, send as plain text
            await update.message.reply_text(chunk)


# ---------------------------------------------------------------
# 14. CALLBACK QUERY ROUTER
# ---------------------------------------------------------------

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route callback queries to the appropriate handler."""
    query = update.callback_query
    data = query.data

    if data.startswith("topic_"):
        await topic_callback(update, context)
    elif data.startswith("quiz_"):
        await quiz_callback(update, context)


# ---------------------------------------------------------------
# 15. MAIN ENTRY POINT
# ---------------------------------------------------------------

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("topics", topics_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("score", score_command))
    app.add_handler(CommandHandler("tip", tip_command))
    app.add_handler(CommandHandler("cve", cve_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("checklist", checklist_command))
    app.add_handler(CommandHandler("reset", reset_command))

    # Callback handler for inline keyboards (topics + quizzes)
    app.add_handler(CallbackQueryHandler(callback_router))

    # Message handler (anything that isn't a command)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 CyberSec Buddy is starting (polling mode)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
