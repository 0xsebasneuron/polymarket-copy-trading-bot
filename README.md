<h1 align="center">Polymarket Analyzer ⚡</h1>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a></p>

<p align="center">Repository: <a href="https://github.com/0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2">0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2</a></p>

<h3>📅 Polymarket CLOB V2 and pUSD (facts from official docs)</h3>

<p>Polymarket’s <strong>CLOB V2</strong> rollout (live <strong>April 28, 2026</strong>) replaced V1 matching and collateral: trading paused for about <strong>one hour</strong> from ~<strong>11:00 UTC</strong>, all resting V1 orders were cleared, and the venue moved to new <strong>CTF Exchange</strong> contracts with <strong>pUSD</strong> (Polymarket USD) as the trading collateral token (1:1 USDC backing enforced on-chain per Polymarket). This repository is the author’s <strong>latest GUI build</strong> aligned with that stack (<code>py-clob-client-v2</code> / <code>https://clob.polymarket.com</code>). Before you extend approvals or balances, diff your code against the current <a href="https://docs.polymarket.com/resources/contracts">contracts table</a>—addresses below are a snapshot from Polymarket’s published docs.</p>

<p>Primary sources: <a href="https://help.polymarket.com/en/articles/14762452-polymarket-exchange-upgrade-april-28-2026">Exchange upgrade (Help Center)</a> · <a href="https://docs.polymarket.com/v2-migration">CLOB V2 migration</a> · <a href="https://docs.polymarket.com/concepts/pusd">pUSD</a> · <a href="https://docs.polymarket.com/resources/contracts">Contracts</a>.</p>

<table>
  <thead>
    <tr>
      <th>Item</th>
      <th>Value (from Polymarket / Polygon references)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Network</td>
      <td>Polygon PoS, <code>chainId</code> <strong>137</strong> (all Polymarket trading contracts are on this chain).</td>
    </tr>
    <tr>
      <td>Upgrade window</td>
      <td><strong>2026-04-28</strong> starting ~<strong>11:00 UTC</strong> — trading paused ~<strong>1 hour</strong>; V1 order books cleared (users must re-place orders after cutover).</td>
    </tr>
    <tr>
      <td>CLOB API (production)</td>
      <td><code>https://clob.polymarket.com</code> — V2 production host per migration guide.</td>
    </tr>
    <tr>
      <td>Python SDK</td>
      <td><strong><code>py-clob-client-v2</code></strong> (legacy <code>py-clob-client</code> is V1-only).</td>
    </tr>
    <tr>
      <td>Collateral token (V2)</td>
      <td><strong>pUSD</strong> — ERC-20, 6 decimals; Polymarket describes 1:1 USDC backing enforced by smart contract (no fractional reserve).</td>
    </tr>
    <tr>
      <td>USDC.e (legacy bridged)</td>
      <td><code>0x2791Bca1f2De4661ED88A30C99A7a9449Aa84174</code> — used in Polymarket’s <code>CollateralOnramp.wrap()</code> examples as the asset wrapped into pUSD. <a href="https://polygonscan.com/token/0x2791Bca1f2De4661ED88A30C99A7a9449Aa84174">Polygonscan</a></td>
    </tr>
    <tr>
      <td>Native USDC (Circle, Polygon)</td>
      <td><code>0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359</code> — Circle’s native USDC on Polygon PoS (settlement standard referenced alongside pUSD in Polymarket collateral documentation). <a href="https://polygonscan.com/token/0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359">Polygonscan</a></td>
    </tr>
    <tr>
      <td>pUSD token (proxy)</td>
      <td><code>0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB</code> — listed as “pUSD — CollateralToken (proxy)” on Polymarket’s contracts page. <a href="https://polygonscan.com/address/0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB">Polygonscan</a></td>
    </tr>
    <tr>
      <td>CollateralOnramp</td>
      <td><code>0x93070a847efEf7F70739046A929D47a521F5B8ee</code> — wraps USDC.e → pUSD per official pUSD examples. <a href="https://polygonscan.com/address/0x93070a847efEf7F70739046A929D47a521F5B8ee">Polygonscan</a></td>
    </tr>
    <tr>
      <td>CTF Exchange V2 (standard)</td>
      <td><code>0xE111180000d2663C0091e4f400237545B87B996B</code> — EIP-712 domain <code>verifyingContract</code> for standard markets (version <code>&quot;2&quot;</code>). <a href="https://polygonscan.com/address/0xE111180000d2663C0091e4f400237545B87B996B">Polygonscan</a></td>
    </tr>
    <tr>
      <td>Neg-risk CTF Exchange V2</td>
      <td><code>0xe2222d279d744050d28e00520010520000310F59</code> — separate <code>verifyingContract</code> for neg-risk markets. <a href="https://polygonscan.com/address/0xe2222d279d744050d28e00520010520000310F59">Polygonscan</a></td>
    </tr>
    <tr>
      <td>V1 CTF Exchange (deprecated)</td>
      <td><code>0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E</code> — shown in migration doc only as the prior EIP-712 <code>verifyingContract</code> for comparison; do not target for new work.</td>
    </tr>
  </tbody>
</table>

<p><em>On-chain addresses can change if Polymarket rotates implementations—treat <a href="https://docs.polymarket.com/resources/contracts">docs.polymarket.com/resources/contracts</a> as canonical when updating <code>PM_RPC_URL</code>, allowance targets, or local ABIs.</em></p>

<h2>🧭 Why this project</h2>

<ul>
  <li><strong>GUI-first workflow:</strong> A lot of Polymarket automation ships as terminal (TUI) tools. This client is aimed at people who want a full desktop UI—both legs, charts, and execution controls in one PyQt window.</li>
  <li><strong>Host close to the venue:</strong> For latency-sensitive CLOB work, run from a VPS in <strong>Ireland</strong> or another nearby region where Polymarket is available and legally usable for you. Round-trip time to the API and relayers materially affects fills.</li>
  <li><strong>Arbitrage-style core:</strong> The stack pairs that UI with cross-leg logic developed against roughly <strong>30 days</strong> of archived 5-minute BTC <em>up / down</em> prints (research data only—markets drift, and past behaviour is not a forecast).</li>
</ul>

<p><strong>Author contact:</strong> Questions, unstable PnL curves, or tuning help—reach out on Telegram: <a href="https://t.me/sebasneuron">@sebasneuron</a>. Many issues boil down to hosting, clock skew, or book configuration and are quick to narrow with logs.</p>

<p>A high-performance Python desktop client and CLI designed for quantitative analysis, real-time visualization, and execution on the <strong>Polymarket Central Limit Order Book (CLOB)</strong>.</p>

<p>This toolkit specifically targets binary up/down markets (e.g., <code>btc-updown-5m-*</code>). It handles active market resolution via the Gamma API, maintains dual-leg WebSocket streams for high-fidelity state management, and provides an integrated execution environment for single-leg CLOB orders with built-in simulation and session logging capabilities.</p>

<blockquote>
  <p><strong>⚠️ Disclaimer:</strong> This is strictly developer tooling for market research and strategy design. Trading prediction markets involves significant risk of capital loss. Not financial advice.</p>
</blockquote>

<hr>

<h2 align="center">📸 Screenshots</h2>

<p align="center"><sub>Polymarket web (reference): portfolio, daily P/L, <em>Bitcoin Up or Down</em> history, and claim flow—similar markets to those this client analyzes.</sub></p>

<p align="center">
  <img src="assets/polymarket-portfolio-overview.jpg" alt="Polymarket portfolio overview" width="32%" />
  &nbsp;
  <img src="assets/polymarket-portfolio-pnl.jpg" alt="Polymarket portfolio and profit-loss chart" width="32%" />
  &nbsp;
  <img src="assets/polymarket-portfolio-growth.jpg" alt="Polymarket portfolio daily growth" width="32%" />
</p>
<p align="center">
  <img src="assets/polymarket-history-btc-updown.png" alt="Polymarket history tab for Bitcoin Up or Down markets" width="48%" />
  &nbsp;
  <img src="assets/polymarket-claim-winnings.png" alt="Polymarket claim winnings modal" width="48%" />
</p>

<hr>

<h2>🛠 System Architecture &amp; Features</h2>

<ul>
  <li><strong>Asynchronous Dual-Leg Streaming:</strong> Utilizes <code>websockets</code> and <code>qasync</code> to maintain non-blocking, real-time updates for both sides of the order book simultaneously within the PyQt event loop.</li>
  <li><strong>Real-Time Spread Computation:</strong> Calculates and visualizes dynamic spreads (<code>mid</code> / <code>1 - mid</code>) using <code>pyqtgraph</code> for low-latency charting.</li>
  <li><strong>Execution Pipeline:</strong> Supports both simulated (paper) and live execution via <code>py-clob-client-v2</code>. Includes proxy approval routing and multi-signature support.</li>
  <li><strong>Secure State Management:</strong> Implements a localized secret enclave using SQLite (<code>db/polymarket_analyzer.sqlite</code>) to prevent <code>.env</code> leakage of private keys.</li>
</ul>

<hr>

<h2>📦 Installation &amp; Setup</h2>

<p><strong>Prerequisites:</strong> Python <strong>3.10+</strong> (recommended: <strong>3.11</strong>). Use an OS-specific command below to install Python, then clone the repo and install dependencies with <code>pip</code>. Verify with <code>python --version</code> (or on Windows, <code>py --version</code>; on Linux sometimes <code>python3 --version</code>).</p>

<h3>1. Install Python (by operating system)</h3>

<h4>Windows 10 / 11</h4>
<p><strong>winget</strong> (often preinstalled):</p>
<pre><code class="language-powershell">winget install -e --id Python.Python.3.11
</code></pre>
<p><strong>Chocolatey</strong> (if installed): <code>choco install python311 -y</code>. Close and reopen the terminal, then confirm <code>python --version</code> or <code>py -3.11 --version</code>.</p>

<h4>macOS</h4>
<p><strong>Homebrew</strong>:</p>
<pre><code class="language-bash">brew install python@3.11
echo 'export PATH="/opt/homebrew/opt/python@3.11/bin:$PATH"' &gt;&gt; ~/.zshrc   # Apple Silicon; use /usr/local on Intel Mac
source ~/.zshrc
python3.11 --version
</code></pre>

<h4>Linux — Debian / Ubuntu</h4>
<pre><code class="language-bash">sudo apt update
sudo apt install -y python3.11 python3-pip
python3.11 --version
</code></pre>
<p>If <code>python3.11</code> is unavailable in your release, use <code>sudo apt install -y python3 python3-pip</code> (3.10+ is acceptable).</p>

<h4>Linux — Fedora</h4>
<pre><code class="language-bash">sudo dnf install -y python3.11
python3.11 --version
</code></pre>

<h4>Linux — Arch Linux</h4>
<pre><code class="language-bash">sudo pacman -S --needed python python-pip
python --version
</code></pre>

<h3>2. Clone this repository</h3>
<pre><code class="language-bash">git clone https://github.com/0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2.git
cd polymarket-arbitrage-copy-trading-bot-V2
</code></pre>
<p><strong>Optional:</strong> create and activate a virtual environment (e.g. <code>python -m venv .venv</code>) if you want project dependencies isolated from your system interpreter.</p>

<h3>3. Install Python dependencies</h3>
<pre><code class="language-bash">python -m pip install --upgrade pip
python -m pip install -r requirements.txt
</code></pre>
<p>On Linux, substitute <code>python3</code> for <code>python</code> if needed.</p>

<h3>One-click install &amp; run</h3>
<p>From the repository root, helper scripts upgrade <code>pip</code>, install <code>requirements.txt</code> into whatever interpreter runs by default (<code>py -3</code> on Windows when the launcher exists, otherwise <code>python</code>; <code>python3</code> or <code>python</code> on macOS / Linux), then start the GUI:</p>
<ul>
  <li><strong>Windows (double-click):</strong> <code>install-and-run.bat</code></li>
  <li><strong>Windows (PowerShell):</strong> <code>.\install-and-run.ps1</code> — if execution policy blocks it: <code>powershell -ExecutionPolicy Bypass -File .\install-and-run.ps1</code></li>
  <li><strong>macOS / Linux:</strong> <code>chmod +x install-and-run.sh</code> once, then <code>./install-and-run.sh</code> — optional args: <code>./install-and-run.sh --symbol sol --interval 5</code></li>
</ul>

<h3>4. Configure &amp; start</h3>
<p>Create a <code>.env</code> file in the project root (same folder as <code>requirements.txt</code>) with at least <code>PM_RPC_URL</code> and any keys described under <em>Environment Configuration</em> below. Then start the desktop app from the repo root:</p>
<pre><code class="language-bash"># Primary way to launch the GUI (defaults: btc, 5-minute interval)
python -m polymarket_analyzer.qt_main

# Optional: pick symbol and interval minutes (1–60)
python -m polymarket_analyzer.qt_main --symbol eth --interval 15

# Headless NDJSON stream (example)
python -m polymarket_analyzer --symbol btc --interval 5
</code></pre>
<p>More options (GUI flags, SQLite helpers, quiet mode) are in the <strong>Usage Guide</strong> section below.</p>

<hr>

<h2>🚀 Usage Guide</h2>

<h3>Desktop GUI (PyQt6)</h3>
<p>Launch the visual analyzer. The GUI utilizes <code>qasync</code> to bridge the <code>asyncio</code> event loop with the Qt application loop, ensuring the UI remains responsive during high-frequency WebSocket updates.</p>

<pre><code class="language-bash"># Recommended entrypoint (same as step 4 above)
python -m polymarket_analyzer.qt_main

# With explicit market symbol and candle interval (minutes)
python -m polymarket_analyzer.qt_main --symbol btc --interval 5

# Alternative: open the same window via the main package
python -m polymarket_analyzer --gui
</code></pre>

<h3>Headless CLI Stream (NDJSON)</h3>
<p>Designed for piping order book data into other services or databases. Outputs structured NDJSON directly to <code>stdout</code>.</p>

<pre><code class="language-bash"># Stream 5-minute BTC market data
python -m polymarket_analyzer --symbol btc --interval 5

# Optional parameters
python -m polymarket_analyzer --symbol eth --interval 15 --duration 60 -q
</code></pre>
<ul>
  <li><code>--duration &lt;seconds&gt;</code>: Gracefully terminate the stream after a set time.</li>
  <li><code>-q</code>: Quiet mode (suppresses non-critical standard logging).</li>
</ul>

<h3>Local Secret Enclave (SQLite)</h3>
<p>Instead of relying on plaintext <code>.env</code> files, you can utilize the internal SQLite store for sensitive configurations.</p>

<pre><code class="language-bash"># Initialize/check database path
python -m polymarket_analyzer --sqlite-path

# Safely inject private key into the local DB
python -m polymarket_analyzer --sqlite-save pm_private_key "0xYourPrivateKeyHere"
</code></pre>

<hr>

<h2>⚙️ Environment Configuration</h2>

<p>On application initialization, <code>python-dotenv</code> loads variables from the current working directory.</p>

<table>
  <thead>
    <tr>
      <th>Variable</th>
      <th>Type</th>
      <th>Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>PM_PRIVATE_KEY</code></td>
      <td><code>Hex String</code></td>
      <td>Private key for CLOB signing. <em>(Aliases: <code>POLYMARKET_PRIVATE_KEY</code>, <code>PRIVATE_KEY</code>)</em></td>
    </tr>
    <tr>
      <td><code>PM_SIG_TYPE</code></td>
      <td><code>Integer</code></td>
      <td><code>0</code> = EOA (Direct) <br> <code>1</code> = POLY_PROXY <br> <code>2</code> = Gnosis Safe</td>
    </tr>
    <tr>
      <td><code>PM_FUNDER</code></td>
      <td><code>Address</code></td>
      <td>Optional. Explicit funder/vault address for margin checks.</td>
    </tr>
    <tr>
      <td><code>PM_RPC_URL</code></td>
      <td><code>URL</code></td>
      <td>Polygon JSON-RPC endpoint for wallet/allowance verification.</td>
    </tr>
    <tr>
      <td><code>PM_SIMULATE</code></td>
      <td><code>Boolean</code></td>
      <td>If truthy (<code>1</code>, <code>true</code>), orders bypass <code>post_order</code> and are logged locally.</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_KEY</code></td>
      <td><code>String</code></td>
      <td>Builder API Key (Required for relayer approvals on sig types 1 / 2).</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_SECRET</code></td>
      <td><code>String</code></td>
      <td>Builder API Secret.</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_PASSPHRASE</code></td>
      <td><code>String</code></td>
      <td>Builder API Passphrase.</td>
    </tr>
  </tbody>
</table>

<blockquote>
  <p><strong>Security Note:</strong> Never commit your <code>.env</code> or the <code>db/polymarket_analyzer.sqlite</code> file. Ensure both are included in your <code>.gitignore</code>.</p>
</blockquote>

<hr>

<h2>📂 Codebase Topology</h2>

<p>The repository is modularized to separate the UI layer from the core execution and chain-interaction logic.</p>

<pre><code>polymarket_analyzer/
├── __init__.py        # Package exports &amp; lazy GUI initialization
├── __main__.py        # CLI router (GUI, NDJSON stream, SQLite config)
├── qt_main.py         # Primary PyQt application entrypoint
├── core/              # Data models, Gamma API logic, OB state, WS sessions
├── trading/           # Spread math, CLOB executor, execution strategies
├── infra/             # Environment configuration mapping &amp; SQLite store
├── chain/             # Web3 interactions (balances, Polygon RPC queries)
└── ui/                # PyQt windows, pyqtgraph instances, async workers
</code></pre>

<hr>

<h2>📄 License</h2>
<p><em>No license file is included. All rights reserved. Do not distribute or utilize in production environments without explicit permission.</em></p>