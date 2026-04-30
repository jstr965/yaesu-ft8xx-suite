"""
Yaesu FT-8XX Suite by K3LH Help Guide
Full how-to guide displayed in a rich-text window from the Help menu.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextBrowser, QLabel, QSplitter, QListWidget, QListWidgetItem,
    QWidget, QFrame
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QColor

APP_VERSION = "2.1.0"
APP_NAME    = "Yaesu FT-8XX Suite by K3LH"

# ─── Help content: each entry is (menu_label, anchor, html_content) ──────────

HELP_SECTIONS = [
    (
        "🚀  Getting Started",
        "getting_started",
        """
        <h2>Getting Started with Yaesu FT-8XX Suite by K3LH</h2>
        <p>Yaesu FT-8XX Suite by K3LH is a fully integrated amateur radio control application
        supporting the <b>Yaesu FT-817, FT-817ND, FT-818, FT-857, FT-857D,
        FT-897, and FT-897D</b>. It combines CAT radio control, digital modes
        (FT8, FT4, JS8, WSPR), contact logging, and spotting networks into
        a single application.</p>

        <h3>Supported Radios</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Radio</th><th>Max Power</th><th>CAT Port</th><th>Hamlib ID</th></tr>
            <tr><td><b>FT-817 / 817ND</b></td><td>5W</td><td>Front 3.5mm DATA jack</td><td>1688</td></tr>
            <tr><td><b>FT-818 / 818ND</b></td><td>6W</td><td>Front 3.5mm DATA jack</td><td>1688</td></tr>
            <tr><td><b>FT-857 / 857D</b></td><td>100W</td><td>Rear 6-pin mini-DIN ACC</td><td>1621</td></tr>
            <tr><td><b>FT-897 / 897D</b></td><td>100W</td><td>Rear DB-9 or 6-pin mini-DIN</td><td>1625</td></tr>
        </table>
        <p>All four radios share the same Yaesu 5-byte CAT protocol, so all features
        work identically across models. Select your radio model in the
        <b>CAT Control</b> tab before connecting.</p>

        <h3>What You Need</h3>
        <ul>
            <li><b>Supported Yaesu radio</b> (FT-817, 818, 857, or 897)</li>
            <li><b>Digirig Mobile</b> (recommended) or any USB CAT + audio interface</li>
            <li><b>WSJT-X</b> installed on your computer (for digital modes)</li>
            <li><b>Windows 10 or 11</b></li>
        </ul>

        <h3>First-Time Setup Checklist</h3>
        <ol>
            <li>Plug in your Digirig and note the COM port in Device Manager</li>
            <li>Connect the radio to the Digirig using the correct cables for your model</li>
            <li>Open the <b>📡 CAT Control</b> tab, select your radio model, then connect</li>
            <li>Open the <b>🔊 Audio</b> tab and start the audio engine</li>
            <li>Open the <b>📶 Digital Modes</b> tab, click <b>⚙ Settings</b>,
                and fill in your callsign, grid square, and WSJT-X path</li>
            <li>Click <b>▶ START ENGINE</b> to begin operating digital modes</li>
        </ol>

        <h3>Quick Start — Making Your First FT8 Contact</h3>
        <ol>
            <li>Connect the radio (CAT Control tab — select model first)</li>
            <li>Go to Digital Modes tab → select <b>FT8</b> and <b>20m</b></li>
            <li>Click <b>QSY Radio →</b> to tune to 14.074 MHz</li>
            <li>Click <b>▶ START ENGINE</b></li>
            <li>Wait for decodes to appear — CQ calls show in <span style="color:#3fb950">green</span></li>
            <li>Double-click a CQ decode to auto-fill the callsign and enable TX</li>
            <li>The engine handles the exchange automatically</li>
            <li>Contact is auto-logged when complete</li>
        </ol>
        """
    ),
    (
        "📡  CAT Control",
        "cat_control",
        """
        <h2>CAT Control</h2>
        <p>CAT (Computer Aided Transceiver) control lets the application remotely
        control your FT-817's frequency, mode, and PTT over a serial connection.</p>

        <h3>Connecting Your Radio</h3>
        <ol>
            <li>Plug in the <b>Digirig</b> USB cable</li>
            <li>Open <b>Device Manager</b> → expand <i>Ports (COM &amp; LPT)</i></li>
            <li>Note the port labeled <b>Silicon Labs CP210x</b> — this is your CAT port</li>
            <li>In the CAT Control tab, select that COM port and set baud to <b>9600</b></li>
            <li>Click <b>▶ CONNECT</b></li>
        </ol>

        <h3>FT-817 Radio Settings</h3>
        <p>Verify these menu settings on the radio itself:</p>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Menu #</th><th>Setting</th><th>Value</th></tr>
            <tr><td>14</td><td>CAT RATE</td><td>9600 bps</td></tr>
            <tr><td>21</td><td>CAT TIME OUT TIMER</td><td>10 msec</td></tr>
            <tr><td>22</td><td>CAT RTS</td><td>ENABLE</td></tr>
        </table>

        <h3>Frequency Control</h3>
        <ul>
            <li><b>Quick Bands</b> — click any band button to jump to that band's start frequency</li>
            <li><b>FT8 Quick-Go</b> — select a band and click Go to jump directly to the FT8 frequency</li>
            <li><b>Manual Entry</b> — type a frequency in MHz (e.g. 14.225000) and press Enter</li>
            <li><b>Step Up/Down</b> — use the ◀◀ ▶▶ buttons with your chosen step size</li>
            <li><b>Memory Channels</b> — one-click recall of common digital/SSB/CW frequencies</li>
        </ul>

        <h3>PTT</h3>
        <p>The large <b>PTT TRANSMIT</b> button keys the radio via CAT command.
        PTT is also controlled automatically by the digital modes engine during FT8/FT4 transmit periods.
        <b>Never click PTT manually while the digital engine is running.</b></p>

        <h3>S-Meter</h3>
        <p>The S-meter polls the radio 4 times per second and displays the received
        signal strength from S0 to S9+60. Values above S9 are shown as S9+dB.</p>
        """
    ),
    (
        "🔊  Audio Setup",
        "audio",
        """
        <h2>Audio Setup</h2>
        <p>Yaesu FT-8XX Suite by K3LH routes audio between your computer's soundcard and the
        FT-817 via the Digirig's built-in USB audio codec.</p>

        <h3>Digirig Audio Wiring</h3>
        <p>The Digirig appears in Windows as <b>"USB Audio Codec"</b> under Sound devices.
        Select this device for <b>both input and output</b> in the Audio tab.</p>

        <h3>FT-817 Cable Connections</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Digirig Jack</th><th>FT-817 Port</th><th>Cable</th></tr>
            <tr><td>AUDIO (3.5mm TRRS)</td><td>DATA (6-pin mini-DIN)</td><td>Digirig FT-817 audio cable</td></tr>
            <tr><td>SERIAL (3.5mm)</td><td>ACC (6-pin mini-DIN)</td><td>Digirig FT-817 CAT cable</td></tr>
        </table>
        <p style="color:#d29922">⚠ Do not swap these cables — the AUDIO and SERIAL jacks are different sizes
        but it's easy to connect them to the wrong FT-817 port.</p>

        <h3>FT-817 Menu Settings for Digital Modes</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Menu #</th><th>Setting</th><th>Value</th></tr>
            <tr><td>03</td><td>DIAL STEP</td><td>100 Hz</td></tr>
            <tr><td>26</td><td>DIG MODE</td><td>USER-U (USB)</td></tr>
            <tr><td>27</td><td>DIG DISP</td><td>0 Hz</td></tr>
            <tr><td>28</td><td>DIG SHIFT</td><td>0 Hz</td></tr>
        </table>
        <p>Set the radio to <b>DIG mode</b> when operating FT8/FT4/WSPR.</p>

        <h3>Gain Controls</h3>
        <ul>
            <li><b>Input gain</b> — adjusts the level of audio coming from the radio into the computer.
                Set so peaks reach 50–70% on the input meter without clipping (red).</li>
            <li><b>Output gain</b> — adjusts audio sent from the computer to the radio TX.
                Start at 100% and reduce if the radio's ALC is peaking.</li>
        </ul>

        <h3>VOX (Voice-Operated TX)</h3>
        <p>When VOX is enabled, the application automatically keys the radio PTT via CAT
        whenever audio is detected above the threshold. This is an alternative to letting
        WSJT-X control PTT directly. <b>Not recommended for digital modes</b> — use CAT PTT instead.</p>

        <h3>Audio Passthrough</h3>
        <p>Enabling <b>Audio Passthrough</b> routes the input device directly to the output device,
        letting you monitor the received audio through your computer speakers. Useful for SSB/CW monitoring.</p>
        """
    ),
    (
        "📶  Digital Modes",
        "digital_modes",
        """
        <h2>Digital Modes (FT8 / FT4 / JS8 / WSPR)</h2>
        <p>Yaesu FT-8XX Suite by K3LH integrates directly with WSJT-X, running it as a hidden background
        process. You never need to open WSJT-X — all decodes, TX control, and logging
        happen inside Yaesu FT-8XX Suite by K3LH.</p>

        <h3>Initial Configuration</h3>
        <p>Click <b>⚙ Settings</b> in the Digital Modes tab and fill in all five tabs:</p>

        <h4>Identity Tab</h4>
        <ul>
            <li><b>Callsign</b> — your full callsign (e.g. K1ABC). Required.</li>
            <li><b>Grid Square</b> — your 4 or 6-character Maidenhead grid locator (e.g. EM72).
                Required for all digital modes. Look yours up at <i>qthlocator.free.fr</i></li>
            <li><b>WSJT-X Path</b> — click <i>Auto-detect</i> or browse to <code>wsjtx.exe</code>.
                Typical location: <code>C:\WSJT\wsjtx\bin\wsjtx.exe</code></li>
        </ul>

        <h4>CAT / Radio Tab</h4>
        <ul>
            <li><b>COM Port</b> — same port used in the CAT Control tab (Silicon Labs CP210x)</li>
            <li><b>Baud Rate</b> — 9600 (must match FT-817 menu #14)</li>
        </ul>

        <h4>Audio Tab</h4>
        <ul>
            <li>Select <b>USB Audio Codec</b> for both input and output</li>
            <li>Click <i>Refresh</i> if the Digirig isn't listed</li>
        </ul>

        <h4>Operating Tab</h4>
        <ul>
            <li><b>Default Mode</b> — FT8 is recommended for most operating</li>
            <li><b>TX/RX Audio Frequency</b> — leave at 1500 Hz (standard)</li>
            <li><b>Frequency Tolerance</b> — 50 Hz is standard</li>
            <li><b>Auto-log QSOs</b> — automatically adds completed contacts to the log</li>
            <li><b>Sync radio frequency</b> — keeps the radio tuned to match WSJT-X</li>
        </ul>

        <h3>Operating Digital Modes</h3>
        <ol>
            <li>Select your mode (FT8/FT4/JS8/WSPR) and band</li>
            <li>Click <b>QSY Radio →</b> to tune to the standard frequency</li>
            <li>Click <b>▶ START ENGINE</b> — WSJT-X launches silently in the background</li>
            <li>Wait for the green <b>● WSJT-X</b> heartbeat indicator to appear</li>
            <li>Decodes appear in the table within the first 15-second period</li>
        </ol>

        <h3>Decode Table Colours</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Colour</th><th>SNR Range</th><th>Meaning</th></tr>
            <tr><td style="background:#0d2b1a">■</td><td>&gt; 0 dB</td><td>Strong signal</td></tr>
            <tr><td style="background:#1a2b0d">■</td><td>−10 to 0 dB</td><td>Good signal</td></tr>
            <tr><td style="background:#2b2a0d">■</td><td>−15 to −10 dB</td><td>Fair signal</td></tr>
            <tr><td style="background:#2a1a0d">■</td><td>−20 to −15 dB</td><td>Weak signal</td></tr>
            <tr><td style="background:#1a1a2b">■</td><td>&lt; −20 dB</td><td>Very weak signal</td></tr>
        </table>
        <p>CQ calls are shown in <span style="color:#3fb950"><b>green bold</b></span>.</p>

        <h3>Replying to a CQ</h3>
        <ul>
            <li><b>Single-click</b> a decode — callsign fills the DX Call box</li>
            <li><b>Double-click</b> a decode — callsign fills AND TX is enabled immediately</li>
            <li>The engine generates the correct exchange messages automatically</li>
        </ul>

        <h3>TX Controls</h3>
        <ul>
            <li><b>ENABLE TX</b> — arms the transmitter; WSJT-X will TX on the next period</li>
            <li><b>HALT TX</b> — immediately stops all transmissions</li>
            <li><b>Free Text</b> — sends a custom message on the next TX period</li>
        </ul>

        <h3>Mode Reference</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Mode</th><th>Period</th><th>Bandwidth</th><th>Best Use</th></tr>
            <tr><td><b>FT8</b></td><td>15s</td><td>50 Hz</td><td>General DX, most popular</td></tr>
            <tr><td><b>FT4</b></td><td>7.5s</td><td>90 Hz</td><td>Contests, faster QSOs</td></tr>
            <tr><td><b>JS8</b></td><td>15s</td><td>50 Hz</td><td>Free-text messaging</td></tr>
            <tr><td><b>WSPR</b></td><td>2 min</td><td>6 Hz</td><td>Propagation beaconing</td></tr>
        </table>

        <h3>Standard Frequencies</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Band</th><th>FT8</th><th>FT4</th><th>WSPR</th><th>JS8</th></tr>
            <tr><td>80m</td><td>3.573</td><td>3.575</td><td>3.5926</td><td>3.578</td></tr>
            <tr><td>40m</td><td>7.074</td><td>7.0475</td><td>7.0386</td><td>7.078</td></tr>
            <tr><td>30m</td><td>10.136</td><td>10.140</td><td>10.1387</td><td>10.130</td></tr>
            <tr><td>20m</td><td>14.074</td><td>14.080</td><td>14.0956</td><td>14.078</td></tr>
            <tr><td>17m</td><td>18.100</td><td>18.104</td><td>18.1046</td><td>18.104</td></tr>
            <tr><td>15m</td><td>21.074</td><td>21.140</td><td>21.0946</td><td>21.078</td></tr>
            <tr><td>10m</td><td>28.074</td><td>28.180</td><td>28.1246</td><td>28.078</td></tr>
            <tr><td>6m</td><td>50.313</td><td>50.318</td><td>50.293</td><td>50.318</td></tr>
        </table>
        <p>All frequencies in MHz. Set radio to <b>DIG mode (USB)</b> for all digital modes.</p>
        """
    ),
    (
        "🗺  Spotting Networks",
        "spotters",
        """
        <h2>Spotting Networks</h2>
        <p>The Spotters tab aggregates live spots from three networks into a single
        colour-coded list. Click any spot to QSY your radio instantly.</p>

        <h3>Network Colour Coding</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr>
                <td style="background:#1a4731; color:#56d364; padding:4px 12px"><b>■ POTA</b></td>
                <td>Parks on the Air activators</td>
            </tr>
            <tr>
                <td style="background:#1a3a5c; color:#79c0ff; padding:4px 12px"><b>■ DX</b></td>
                <td>DX Cluster spots via telnet</td>
            </tr>
            <tr>
                <td style="background:#5c3a1a; color:#f0c040; padding:4px 12px"><b>■ RBN</b></td>
                <td>Reverse Beacon Network (CW/digital skimmer)</td>
            </tr>
        </table>

        <h3>POTA (Parks on the Air)</h3>
        <ul>
            <li>Polls <code>api.pota.app</code> once per minute (respects their rate limit)</li>
            <li>No login required — just click <b>▶ Start</b></li>
            <li>Shows activator callsign, park reference (K-xxxx), park name, QSO count</li>
            <li>Click <b>ℹ Park Info</b> on a selected spot to fetch full park details</li>
        </ul>

        <h3>DX Cluster</h3>
        <ul>
            <li>Connects via telnet to your chosen cluster server</li>
            <li>Enter your callsign — the app logs in automatically</li>
            <li>Raw telnet feed is shown at the bottom of the panel</li>
            <li>Available servers: DXHeat, VE7CC, DX Summit, GB7DXC, WA9PIE, K3LR, W3LPL</li>
        </ul>

        <h3>RBN (Reverse Beacon Network)</h3>
        <ul>
            <li>Connects to <code>telnet.reversebeacon.net:7000</code></li>
            <li>Shows SNR in dB and CW speed (WPM) for each spotted signal</li>
            <li>Excellent for checking if your signal is being heard before calling CQ</li>
            <li>Enter your callsign and click <b>▶ Connect</b></li>
        </ul>

        <h3>Clicking a Spot</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Action</th><th>Result</th></tr>
            <tr><td>Single click</td><td>Shows spot detail and enables action buttons</td></tr>
            <tr><td>Double click</td><td>Instantly QSYs radio to that frequency and mode</td></tr>
            <tr><td>📡 QSY Radio</td><td>Tunes radio to spot frequency, sets mode</td></tr>
            <tr><td>📒 Pre-fill Log</td><td>Opens log dialog pre-filled with callsign, freq, mode</td></tr>
            <tr><td>ℹ Park Info</td><td>POTA only — fetches full park details from API</td></tr>
        </table>

        <h3>Filters</h3>
        <p>Use the filter bar to narrow spots by:</p>
        <ul>
            <li><b>Network</b> — show only POTA, DX, or RBN spots</li>
            <li><b>Band</b> — filter to a specific amateur band</li>
            <li><b>Mode</b> — show only FT8, CW, SSB, etc.</li>
            <li><b>Search</b> — free text search across callsign, park reference, and comment</li>
        </ul>
        """
    ),
    (
        "📒  Contact Log",
        "logging",
        """
        <h2>Contact Log</h2>
        <p>Yaesu FT-8XX Suite by K3LH includes a full QSO logger that stores contacts locally
        and supports ADIF import/export for use with other logging software.</p>

        <h3>Logging a Contact</h3>
        <ul>
            <li><b>Auto-log</b> — when the digital modes engine is running with
                <i>Auto-log QSOs</i> enabled, contacts are logged automatically
                when WSJT-X completes an exchange</li>
            <li><b>Quick Log</b> — use the Quick Log box in the Digital Modes tab
                to manually log with one click</li>
            <li><b>Manual entry</b> — click <b>➕ Log QSO</b> in the Log tab for a
                full entry form. If your radio is connected, frequency and mode
                are pre-filled automatically</li>
        </ul>

        <h3>Log Entry Fields</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Field</th><th>Description</th></tr>
            <tr><td>Callsign</td><td>Station worked (automatically uppercased)</td></tr>
            <tr><td>Frequency</td><td>In MHz — pre-filled from radio if connected</td></tr>
            <tr><td>Mode</td><td>Operating mode (FT8, USB, CW, etc.)</td></tr>
            <tr><td>Band</td><td>Derived automatically from frequency</td></tr>
            <tr><td>RST Sent/Rcvd</td><td>Signal report — for FT8 use SNR value (e.g. -10)</td></tr>
            <tr><td>Grid Square</td><td>Their Maidenhead grid locator</td></tr>
            <tr><td>Notes</td><td>Free text — POTA reference, park name, etc. are auto-filled</td></tr>
        </table>

        <h3>Searching and Filtering</h3>
        <p>Use the <b>Search</b> box above the log table to filter by callsign, band, mode,
        grid, or any other field in real time.</p>

        <h3>Editing and Deleting</h3>
        <ul>
            <li><b>Double-click</b> any row to open the edit dialog</li>
            <li>Select a row and click <b>✏ Edit</b> or <b>🗑 Delete</b></li>
        </ul>

        <h3>ADIF Export</h3>
        <p>Go to <b>File → Export Log (ADIF)…</b> or press <b>Ctrl+E</b>.
        The exported .adi file is compatible with:</p>
        <ul>
            <li>LOTW (Logbook of the World)</li>
            <li>eQSL</li>
            <li>QRZ.com logbook</li>
            <li>Club Log</li>
            <li>Any ADIF-compatible logging software (Log4OM, N1MM+, DXKeeper, etc.)</li>
        </ul>

        <h3>ADIF Import</h3>
        <p>Go to <b>File → Import Log (ADIF)…</b> to import contacts from an existing
        ADIF file. Imported contacts are merged into the existing log.</p>

        <h3>Statistics</h3>
        <p>The statistics bar at the bottom of the log shows total QSOs, number of
        unique bands worked, unique modes, and DXCC entity count.</p>
        """
    ),
    (
        "🌙  Themes",
        "themes",
        """
        <h2>Display Themes</h2>
        <p>Yaesu FT-8XX Suite by K3LH supports three display themes accessible from the
        <b>View</b> menu or the toolbar buttons.</p>

        <h3>Available Themes</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Theme</th><th>Description</th><th>Best For</th></tr>
            <tr>
                <td><b>🌙 Dark</b></td>
                <td>Deep dark background, green/blue accents</td>
                <td>General use, low-light environments</td>
            </tr>
            <tr>
                <td><b>☀️ Light</b></td>
                <td>Clean white/grey interface</td>
                <td>Bright rooms, outdoor use</td>
            </tr>
            <tr>
                <td><b>🔴 Night</b></td>
                <td>Deep red-tinted display</td>
                <td>Dark operating environments, preserves night vision</td>
            </tr>
        </table>

        <p>The <b>Night</b> theme is specifically designed for operating in the dark —
        red light has minimal impact on dark-adapted vision compared to white or blue light.
        All UI elements including the frequency display, meters, and decode table
        use red tones in this mode.</p>

        <p>Theme selection is applied instantly and persists for the session.
        Switch themes at any time using <b>View → [Theme Name] Mode</b>.</p>
        """
    ),
    (
        "🔧  Digirig Setup",
        "digirig",
        """
        <h2>Digirig Mobile Setup</h2>
        <p>The Digirig Mobile is the recommended interface for use with Yaesu FT-8XX Suite by K3LH.
        It provides both CAT serial control and audio in a single USB device.</p>

        <h3>What the Digirig Provides</h3>
        <ul>
            <li><b>USB Serial port</b> — for CAT control (appears as Silicon Labs CP210x)</li>
            <li><b>USB Audio Codec</b> — for digital mode audio TX/RX</li>
            <li><b>PTT</b> — controlled via RTS signal on the serial port (CAT PTT)</li>
        </ul>

        <h3>Cable Connections to FT-817</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Digirig Port</th><th>FT-817 Port</th><th>Purpose</th></tr>
            <tr><td>AUDIO (TRRS 3.5mm)</td><td>DATA (6-pin mini-DIN)</td><td>TX/RX audio for digital modes</td></tr>
            <tr><td>SERIAL (3.5mm)</td><td>ACC (6-pin mini-DIN)</td><td>CAT control &amp; PTT</td></tr>
        </table>

        <h3>Windows Driver Installation</h3>
        <ol>
            <li>Plug in the Digirig USB cable</li>
            <li>Windows should auto-install the CP210x driver</li>
            <li>If not, download from: <i>silabs.com/developers/usb-to-uart-bridge-vcp-drivers</i></li>
            <li>After install, the COM port appears in Device Manager under <i>Ports (COM &amp; LPT)</i></li>
        </ol>

        <h3>Verifying the Setup</h3>
        <ol>
            <li>Open Device Manager</li>
            <li>Expand <b>Ports (COM &amp; LPT)</b> — note the COM number for <i>Silicon Labs CP210x</i></li>
            <li>Expand <b>Sound, video and game controllers</b> — you should see <i>USB Audio Codec</i></li>
            <li>Use these in the CAT Control and Audio tabs respectively</li>
        </ol>

        <h3>RFI / Noise Issues</h3>
        <p>If you experience audio noise or the CAT connection drops during transmit:</p>
        <ul>
            <li>Use a <b>USB isolator</b> between the Digirig and your computer</li>
            <li>Try a different USB port or USB hub with individual power switching</li>
            <li>Ensure the FT-817 and computer share a common ground</li>
            <li>Add ferrite chokes to the USB cable near both ends</li>
        </ul>

        <h3>Recommended Digirig Cable Kit for FT-817</h3>
        <p>Order the <b>FT-817/818/857/897 cable kit</b> from <i>digirig.net</i> — it includes
        both the DATA cable and the ACC CAT cable pre-wired for the FT-817's mini-DIN connectors.</p>
        """
    ),
    (
        "❓  Troubleshooting",
        "troubleshooting",
        """
        <h2>Troubleshooting</h2>

        <h3>Radio Won't Connect</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Symptom</th><th>Fix</th></tr>
            <tr><td>Wrong COM port selected</td><td>Check Device Manager for the correct CP210x port number</td></tr>
            <tr><td>Baud rate mismatch</td><td>Check FT-817 menu #14 — must match (default 9600)</td></tr>
            <tr><td>Port in use by another app</td><td>Close other CAT applications (WSJT-X standalone, flrig, etc.)</td></tr>
            <tr><td>Radio off or cable unplugged</td><td>Verify power and cable connections</td></tr>
        </table>

        <h3>Digital Engine Won't Start</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Symptom</th><th>Fix</th></tr>
            <tr><td>WSJT-X not found</td><td>Click ⚙ Settings → Identity → Auto-detect, or browse to wsjtx.exe</td></tr>
            <tr><td>No callsign set</td><td>Required — enter your callsign in ⚙ Settings → Identity</td></tr>
            <tr><td>No grid set</td><td>Required — enter your 4 or 6-character grid square</td></tr>
            <tr><td>UDP port conflict</td><td>Another WSJT-X may be running — close it, or change the port in Network settings</td></tr>
        </table>

        <h3>No Decodes Appearing</h3>
        <ul>
            <li>Check that the radio is in <b>DIG mode</b> (not USB or LSB)</li>
            <li>Verify audio input device is set to <b>USB Audio Codec</b> in ⚙ Settings → Audio</li>
            <li>Check the input level meter in the Audio tab — should show activity when band is busy</li>
            <li>Ensure you are on a standard FT8/FT4 frequency</li>
            <li>The engine needs to be connected (green ● WSJT-X indicator in Digital Modes tab)</li>
        </ul>

        <h3>Audio Issues</h3>
        <ul>
            <li><b>No TX audio</b> — check output device is USB Audio Codec in ⚙ Settings → Audio</li>
            <li><b>Distorted TX</b> — reduce output gain in the Audio tab; check ALC on radio</li>
            <li><b>No RX audio</b> — check input device; verify Digirig DATA cable is connected to FT-817</li>
            <li><b>Hum or noise</b> — use a USB isolator; add ferrite chokes to USB cable</li>
        </ul>

        <h3>POTA Spots Not Loading</h3>
        <ul>
            <li>Check internet connection</li>
            <li>POTA API may be temporarily unavailable — try again in a few minutes</li>
            <li>Firewall may be blocking outbound HTTP — allow Python through Windows Firewall</li>
        </ul>

        <h3>Application Crashes on Start</h3>
        <ul>
            <li>Run from Command Prompt to see the error: <code>python main.py</code></li>
            <li>Ensure all dependencies are installed: <code>pip install PyQt6 pyserial sounddevice numpy scipy</code></li>
            <li>Python 3.11 or 3.12 is recommended — Python 3.14 may have PyQt6 compatibility issues</li>
        </ul>
        """
    ),
    (
        "ℹ️  About",
        "about",
        f"""
        <h2>Yaesu FT-8XX Suite by K3LH  v{APP_VERSION}</h2>
        <p>Yaesu FT-8XX Suite by K3LH</p>

        <h3>Supported Radios</h3>
        <ul>
            <li>Yaesu FT-817 / FT-817ND (5W QRP)</li>
            <li>Yaesu FT-818 / FT-818ND (6W QRP)</li>
            <li>Yaesu FT-857 / FT-857D (100W mobile)</li>
            <li>Yaesu FT-897 / FT-897D (100W base/portable)</li>
        </ul>

        <h3>Features</h3>
        <ul>
            <li>CAT control — frequency, mode, PTT, S-meter (all models)</li>
            <li>Computer soundcard audio I/O via Digirig or any USB audio interface</li>
            <li>Integrated FT8, FT4, JS8, WSPR digital modes (hidden WSJT-X engine)</li>
            <li>Live spotting: POTA, DX Cluster telnet, RBN</li>
            <li>QSO logger with ADIF import/export</li>
            <li>Dark, Light and Night (red) display themes</li>
            <li>Real-time spectrum and waterfall display</li>
        </ul>

        <h3>Version History</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Version</th><th>Changes</th></tr>
            <tr><td><b>2.1.0</b></td><td>Supply voltage display in header bar (VDC readout
                via 0xA7 CAT command, colour-coded by level, polls every 10s),
                responsive layout fixes across all panels, multi-radio support
                fully wired end-to-end</td></tr>
            <tr><td>2.0.0</td><td>Multi-radio support (FT-817/818/857/897),
                integrated WSJT-X engine, POTA/DX Cluster/RBN spotters,
                settings dialog, Night theme, help guide, responsive layout</td></tr>
            <tr><td>1.0.0</td><td>Initial release — FT-817 CAT control, audio,
                basic WSJT-X UDP integration, logging</td></tr>
        </table>

        <h3>Dependencies</h3>
        <table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;">
            <tr><th>Package</th><th>Purpose</th></tr>
            <tr><td>PyQt6</td><td>User interface framework</td></tr>
            <tr><td>pyserial</td><td>Serial port (CAT control)</td></tr>
            <tr><td>sounddevice</td><td>Audio I/O</td></tr>
            <tr><td>numpy</td><td>FFT / waterfall processing</td></tr>
            <tr><td>scipy</td><td>Audio DSP filters</td></tr>
            <tr><td>WSJT-X</td><td>Digital mode codec engine (separate install)</td></tr>
        </table>

        <h3>WSJT-X</h3>
        <p>WSJT-X is developed by Joe Taylor K1JT and the WSJT Development Group.
        Yaesu FT-8XX Suite by K3LH uses WSJT-X as a background engine via its UDP protocol interface.
        Download WSJT-X from: <i>physics.princeton.edu/pulsar/K1JT/wsjtx.html</i></p>

        <h3>License</h3>
        <p>Yaesu FT-8XX Suite by K3LH is free software for amateur radio use.</p>
        """
    ),
]


class HelpWindow(QDialog):
    """
    Full help guide window with sidebar navigation and rich HTML content.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Yaesu FT-8XX Suite by K3LH  v{APP_VERSION}  —  Help Guide")
        self.setMinimumSize(900, 650)
        self.resize(1000, 700)
        self._build_ui()
        # Show first section
        self.nav_list.setCurrentRow(0)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(
            "background: #1f2937; border-bottom: 1px solid #30363d;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel(f"  📖  Yaesu FT-8XX Suite by K3LH  —  Help Guide  —  v{APP_VERSION}")
        title.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e6edf3; letter-spacing: 1px;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        btn_close = QPushButton("✕  Close")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.accept)
        h_layout.addWidget(btn_close)
        layout.addWidget(header)

        # Splitter: nav list + content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        # Left nav
        nav_widget = QWidget()
        nav_widget.setFixedWidth(200)
        nav_widget.setStyleSheet("background: #161b22;")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(0)

        nav_label = QLabel("  CONTENTS")
        nav_label.setStyleSheet(
            "font-size: 9px; font-weight: bold; color: #484f58; "
            "letter-spacing: 2px; padding: 8px 12px 4px;")
        nav_layout.addWidget(nav_label)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 9px 16px;
                color: #8b949e;
                font-size: 11px;
                border-left: 3px solid transparent;
            }
            QListWidget::item:selected {
                background: #1f2937;
                color: #e6edf3;
                border-left: 3px solid #1f6feb;
                font-weight: bold;
            }
            QListWidget::item:hover:!selected {
                background: #1c2128;
                color: #c9d1d9;
            }
        """)
        self.nav_list.setFont(QFont("Consolas", 10))

        for label, anchor, _ in HELP_SECTIONS:
            item = QListWidgetItem(label)
            self.nav_list.addItem(item)

        self.nav_list.currentRowChanged.connect(self._show_section)
        nav_layout.addWidget(self.nav_list, 1)
        splitter.addWidget(nav_widget)

        # Right content
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet("""
            QTextBrowser {
                background: #0d1117;
                color: #c9d1d9;
                border: none;
                padding: 24px 32px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
                line-height: 1.6;
            }
        """)
        self.browser.document().setDefaultStyleSheet("""
            h2 { color: #e6edf3; font-size: 20px; margin-bottom: 8px;
                 border-bottom: 1px solid #30363d; padding-bottom: 8px; }
            h3 { color: #58a6ff; font-size: 14px; margin-top: 18px; margin-bottom: 6px; }
            h4 { color: #d2a8ff; font-size: 12px; margin-top: 12px; margin-bottom: 4px; }
            p  { color: #c9d1d9; line-height: 1.7; margin-bottom: 10px; }
            li { color: #c9d1d9; line-height: 1.8; }
            b  { color: #e6edf3; }
            code { background: #161b22; color: #79c0ff;
                   padding: 1px 6px; border-radius: 3px;
                   font-family: Consolas, monospace; font-size: 11px; }
            i  { color: #8b949e; }
            table { border-collapse: collapse; margin: 10px 0; width: 100%; }
            th { background: #21262d; color: #8b949e; padding: 7px 12px;
                 font-size: 10px; text-transform: uppercase; letter-spacing: 1px;
                 border: 1px solid #30363d; }
            td { padding: 6px 12px; border: 1px solid #30363d; color: #c9d1d9; }
            tr:nth-child(even) td { background: #161b22; }
        """)
        content_layout.addWidget(self.browser)

        # Bottom nav buttons
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(16, 8, 16, 8)
        self.btn_prev = QPushButton("◀  Previous")
        self.btn_prev.clicked.connect(self._prev_section)
        self.btn_next = QPushButton("Next  ▶")
        self.btn_next.clicked.connect(self._next_section)
        btn_bar.addWidget(self.btn_prev)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_next)
        content_layout.addLayout(btn_bar)

        splitter.addWidget(content_widget)
        splitter.setSizes([200, 800])

    def _show_section(self, index: int):
        if 0 <= index < len(HELP_SECTIONS):
            _, _, html = HELP_SECTIONS[index]
            self.browser.setHtml(html)
            self.browser.verticalScrollBar().setValue(0)
            self.btn_prev.setEnabled(index > 0)
            self.btn_next.setEnabled(index < len(HELP_SECTIONS) - 1)

    def _prev_section(self):
        row = self.nav_list.currentRow()
        if row > 0:
            self.nav_list.setCurrentRow(row - 1)

    def _next_section(self):
        row = self.nav_list.currentRow()
        if row < len(HELP_SECTIONS) - 1:
            self.nav_list.setCurrentRow(row + 1)
