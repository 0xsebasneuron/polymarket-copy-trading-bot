<h1 align="center">Polymarket Analyzer ⚡</h1>

<p align="center"><a href="README.md">English</a> · <b>简体中文</b> · <a href="README.ru.md">Русский</a></p>

<p align="center">源码仓库：<a href="https://github.com/0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2">0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2</a></p>

<h3>📅 Polymarket CLOB V2 与 pUSD（官方文档数据）</h3>

<p>Polymarket 在 <strong>2026 年 4 月 28 日</strong>上线 <strong>CLOB V2</strong>：更换撮合与保证金体系；当日约自 <strong>11:00 UTC</strong> 起暂停交易约 <strong>1 小时</strong>，V1 挂单全部清空，需用 V2 规则重新下单。新抵押代币为 <strong>pUSD</strong>（Polymarket USD），官方说明为链上强制 1:1 USDC 支持的 ERC-20。本仓库为作者维护的、与该栈一致的<strong>最新 GUI 版本</strong>（<code>py-clob-client-v2</code> / <code>https://clob.polymarket.com</code>）。扩展授权或余额逻辑前，请以 Polymarket 当前 <a href="https://docs.polymarket.com/resources/contracts">合约表</a>为准核对地址。</p>

<p>官方出处：<a href="https://help.polymarket.com/en/articles/14762452-polymarket-exchange-upgrade-april-28-2026">升级说明（Help Center）</a> · <a href="https://docs.polymarket.com/v2-migration">CLOB V2 迁移</a> · <a href="https://docs.polymarket.com/concepts/pusd">pUSD</a> · <a href="https://docs.polymarket.com/resources/contracts">合约地址</a>。</p>

<table>
  <thead>
    <tr>
      <th>项目</th>
      <th>数值（摘自 Polymarket / Polygon 公开资料）</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>网络</td>
      <td>Polygon PoS，<code>chainId</code> <strong>137</strong>（Polymarket 交易合约均部署于此链）。</td>
    </tr>
    <tr>
      <td>升级窗口</td>
      <td><strong>2026-04-28</strong> 约 <strong>11:00 UTC</strong> 起暂停约 <strong>1 小时</strong>；V1 订单簿清空（需在升级后重新挂单）。</td>
    </tr>
    <tr>
      <td>CLOB 生产 API</td>
      <td><code>https://clob.polymarket.com</code> — 迁移文档中的 V2 生产环境主机。</td>
    </tr>
    <tr>
      <td>Python SDK</td>
      <td><strong><code>py-clob-client-v2</code></strong>（旧版 <code>py-clob-client</code> 仅面向 V1）。</td>
    </tr>
    <tr>
      <td>抵押代币（V2）</td>
      <td><strong>pUSD</strong> — ERC-20，6 位小数；Polymarket 描述为链上强制 1:1 USDC 支持。</td>
    </tr>
    <tr>
      <td>USDC.e（旧版桥接）</td>
      <td><code>0x2791Bca1f2De4661ED88A30C99A7a9449Aa84174</code> — 官方 <code>CollateralOnramp.wrap()</code> 示例中作为被 wrap 的资产。 <a href="https://polygonscan.com/token/0x2791Bca1f2De4661ED88A30C99A7a9449Aa84174">Polygonscan</a></td>
    </tr>
    <tr>
      <td>原生 USDC（Circle，Polygon）</td>
      <td><code>0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359</code> — Circle 在 Polygon PoS 上的原生 USDC（与 pUSD 文档中“原生 USDC 结算”表述一致的行业标准参考）。 <a href="https://polygonscan.com/token/0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359">Polygonscan</a></td>
    </tr>
    <tr>
      <td>pUSD 代币（代理）</td>
      <td><code>0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB</code> — Polymarket 合约页中的 “pUSD — CollateralToken (proxy)”。 <a href="https://polygonscan.com/address/0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB">Polygonscan</a></td>
    </tr>
    <tr>
      <td>CollateralOnramp</td>
      <td><code>0x93070a847efEf7F70739046A929D47a521F5B8ee</code> — 官方示例：将 USDC.e wrap 为 pUSD。 <a href="https://polygonscan.com/address/0x93070a847efEf7F70739046A929D47a521F5B8ee">Polygonscan</a></td>
    </tr>
    <tr>
      <td>CTF Exchange V2（标准市场）</td>
      <td><code>0xE111180000d2663C0091e4f400237545B87B996B</code> — 标准市场 EIP-712 域 <code>verifyingContract</code>（版本 <code>&quot;2&quot;</code>）。 <a href="https://polygonscan.com/address/0xE111180000d2663C0091e4f400237545B87B996B">Polygonscan</a></td>
    </tr>
    <tr>
      <td>Neg-risk CTF Exchange V2</td>
      <td><code>0xe2222d279d744050d28e00520010520000310F59</code> — neg-risk 市场单独 <code>verifyingContract</code>。 <a href="https://polygonscan.com/address/0xe2222d279d744050d28e00520010520000310F59">Polygonscan</a></td>
    </tr>
    <tr>
      <td>V1 CTF Exchange（已弃用）</td>
      <td><code>0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E</code> — 迁移文档中仅作对照的旧 EIP-712 合约，勿用于新集成。</td>
    </tr>
  </tbody>
</table>

<p><em>若 Polymarket 轮换实现合约，地址可能更新——更新 <code>PM_RPC_URL</code>、授权目标或本地 ABI 时，请以 <a href="https://docs.polymarket.com/resources/contracts">docs.polymarket.com/resources/contracts</a> 为准。</em></p>

<h2>🧭 项目说明</h2>
<ul>
  <li><strong>图形界面优先：</strong>不少 Polymarket 自动化以终端（TUI）为主；本工具面向更偏好完整桌面 UI 的用户——双腿盘口、图表与执行控制在同一 PyQt 窗口内完成。</li>
  <li><strong>部署尽量靠近交易端：</strong>对延迟敏感的 CLOB 场景，建议在 <strong>爱尔兰</strong> 或邻近、且在你所在地合规可用的区域使用 VPS；到 API 与中继的往返时延会明显影响成交。</li>
  <li><strong>套利向的核心逻辑：</strong>界面与跨腿逻辑配套开发，并基于约 <strong>30 天</strong> 归档的 5 分钟 BTC 涨跌行情数据做研究迭代（仅供研究，市场会变化，历史表现不代表未来）。</li>
</ul>

<p><strong>作者联系：</strong>若曲线不稳定、需要排查或参数调优，可通过 Telegram 联系：<a href="https://t.me/sebasneuron">@sebasneuron</a>。很多问题与机房位置、时钟偏差或盘口配置有关，结合日志通常能较快定位。</p>

<p>面向 <strong>Polymarket 中央限价订单簿（CLOB）</strong> 的量化分析、实时可视化与交易执行而设计的高性能 Python 桌面客户端与命令行工具。</p>

<p>本工具聚焦二元涨跌市场（例如 <code>btc-updown-5m-*</code>）：通过 Gamma API 解析活跃市场，以双通道 WebSocket 维护订单簿状态，并集成单腿 CLOB 下单、模拟成交与会话日志。</p>

<blockquote>
  <p><strong>⚠️ 免责声明：</strong>本项目仅供开发者做市场研究与策略设计，不构成投资建议。参与预测市场交易可能导致本金重大损失。</p>
</blockquote>

<hr>

<h2 align="center">📸 界面截图</h2>

<p align="center"><sub>以下为 Polymarket 网页端参考界面：资产组合、当日盈亏、<em>Bitcoin Up or Down</em> 成交历史与领奖流程，与本工具所针对的市场类型一致。</sub></p>

<p align="center">
  <img src="assets/polymarket-portfolio-overview.jpg" alt="Polymarket 资产组合总览" width="32%" />
  &nbsp;
  <img src="assets/polymarket-portfolio-pnl.jpg" alt="Polymarket 资产与盈亏曲线" width="32%" />
  &nbsp;
  <img src="assets/polymarket-portfolio-growth.jpg" alt="Polymarket 资产单日涨幅" width="32%" />
</p>
<p align="center">
  <img src="assets/polymarket-history-btc-updown.png" alt="Polymarket 历史记录：比特币涨跌市场" width="48%" />
  &nbsp;
  <img src="assets/polymarket-claim-winnings.png" alt="Polymarket 领取收益弹窗" width="48%" />
</p>

<hr>

<h2>🛠 系统架构与特性</h2>

<ul>
  <li><strong>异步双腿流式行情：</strong>结合 <code>websockets</code> 与 <code>qasync</code>，在 PyQt 事件循环内对订单簿两侧进行非阻塞、同步高频更新。</li>
  <li><strong>实时价差计算：</strong>计算并绘制动态价差（<code>mid</code> / <code>1 - mid</code>），使用 <code>pyqtgraph</code> 降低绘图延迟。</li>
  <li><strong>执行管线：</strong>通过 <code>py-clob-client-v2</code> 支持模拟盘与实盘；包含代理授权路由及多签场景支持。</li>
  <li><strong>安全状态管理：</strong>使用本地 SQLite（<code>db/polymarket_analyzer.sqlite</code>）作为密钥存储，降低 <code>.env</code> 泄露私钥的风险。</li>
</ul>

<hr>

<h2>📦 安装与环境</h2>

<p><strong>环境要求：</strong> Python <strong>3.10+</strong>（推荐 <strong>3.11</strong>）。按系统装好 Python，克隆仓库后用 <code>pip</code> 安装依赖。可用 <code>python --version</code>（Windows 还可试 <code>py --version</code>；Linux 常用 <code>python3 --version</code>）确认版本。</p>

<h3>1. 安装 Python（按系统选择）</h3>

<h4>Windows 10 / 11</h4>
<p><strong>winget</strong>（较新系统通常自带）：</p>
<pre><code class="language-powershell">winget install -e --id Python.Python.3.11
</code></pre>
<p><strong>Chocolatey</strong>（若已安装）：<code>choco install python311 -y</code>。关闭并重开终端后执行 <code>python --version</code> 或 <code>py -3.11 --version</code>。</p>

<h4>macOS</h4>
<p><strong>Homebrew</strong>：</p>
<pre><code class="language-bash">brew install python@3.11
echo 'export PATH="/opt/homebrew/opt/python@3.11/bin:$PATH"' &gt;&gt; ~/.zshrc   # Apple Silicon；Intel Mac 多为 /usr/local/opt/...
source ~/.zshrc
python3.11 --version
</code></pre>

<h4>Linux — Debian / Ubuntu</h4>
<pre><code class="language-bash">sudo apt update
sudo apt install -y python3.11 python3-pip
python3.11 --version
</code></pre>
<p>若软件源无 3.11，可使用 <code>sudo apt install -y python3 python3-pip</code>（满足 3.10+ 即可）。</p>

<h4>Linux — Fedora</h4>
<pre><code class="language-bash">sudo dnf install -y python3.11
python3.11 --version
</code></pre>

<h4>Linux — Arch</h4>
<pre><code class="language-bash">sudo pacman -S --needed python python-pip
python --version
</code></pre>

<h3>2. 克隆本仓库</h3>
<pre><code class="language-bash">git clone https://github.com/0xsebasneuron/polymarket-arbitrage-copy-trading-bot-V2.git
cd polymarket-arbitrage-copy-trading-bot-V2
</code></pre>
<p><strong>可选：</strong>若希望依赖与系统 Python 隔离，可自行创建并激活虚拟环境（例如 <code>python -m venv .venv</code>）。</p>

<h3>3. 安装依赖</h3>
<pre><code class="language-bash">python -m pip install --upgrade pip
python -m pip install -r requirements.txt
</code></pre>
<p>在 Linux 上若需使用 <code>python3</code>，请把上述命令中的 <code>python</code> 换成 <code>python3</code>。</p>

<h3>一键安装并启动</h3>
<p>在仓库根目录，脚本分三步：<strong>尽量安装 Python</strong>（<strong>Windows</strong>：若无 <code>py</code>/<code>python</code> 且存在 winget，则安装 <code>Python.Python.3.11</code> 并在当前会话刷新 PATH；<strong>macOS</strong>：有 Homebrew 时 <code>brew install</code>；<strong>Debian/Ubuntu</strong>：<code>sudo apt-get install</code> <code>python3</code> 与 pip）；然后升级 <code>pip</code> 并安装 <code>requirements.txt</code>；最后执行 <code>python -m polymarket_analyzer.qt_main</code>（Windows 上通常为 <code>py -3</code>）。若自动安装失败，请手动装好 Python 后重试：</p>
<ul>
  <li><strong>Windows（双击）：</strong><code>install-and-run.bat</code></li>
  <li><strong>Windows（PowerShell）：</strong><code>.\install-and-run.ps1</code>；若策略拦截：<code>powershell -ExecutionPolicy Bypass -File .\install-and-run.ps1</code></li>
  <li><strong>macOS / Linux：</strong>首次 <code>chmod +x install-and-run.sh</code>，之后 <code>./install-and-run.sh</code>；可带参数，如 <code>./install-and-run.sh --symbol sol --interval 5</code></li>
</ul>

<h3>4. 配置并启动</h3>
<p>在仓库根目录（与 <code>requirements.txt</code> 同级）创建 <code>.env</code>，至少配置 <code>PM_RPC_URL</code> 及下文「环境变量」中的密钥项。然后在仓库根目录启动桌面端：</p>
<pre><code class="language-bash"># 推荐：专用 GUI 入口（默认 btc、5 分钟周期）
python -m polymarket_analyzer.qt_main

# 可选：指定标的与周期（分钟 1–60）
python -m polymarket_analyzer.qt_main --symbol eth --interval 15

# 命令行 NDJSON 流（示例）
python -m polymarket_analyzer --symbol btc --interval 5
</code></pre>
<p>更多参数见下文「使用说明」。</p>

<hr>

<h2>🚀 使用说明</h2>

<h3>桌面图形界面（PyQt6）</h3>
<p>启动可视化分析端。界面通过 <code>qasync</code> 将 <code>asyncio</code> 与 Qt 主循环桥接，在高频 WebSocket 推送下仍保持界面响应。</p>

<pre><code class="language-bash"># 推荐入口（与上文「配置并启动」一致）
python -m polymarket_analyzer.qt_main

# 显式指定标的与 K 线周期（分钟）
python -m polymarket_analyzer.qt_main --symbol btc --interval 5

# 备选：通过主包加 --gui 打开同一窗口
python -m polymarket_analyzer --gui
</code></pre>

<h3>无头 CLI 流（NDJSON）</h3>
<p>便于将订单簿数据管道到其他服务或数据库，将结构化 NDJSON 输出到 <code>stdout</code>。</p>

<pre><code class="language-bash"># 流式输出 5 分钟 BTC 市场
python -m polymarket_analyzer --symbol btc --interval 5

# 可选参数
python -m polymarket_analyzer --symbol eth --interval 15 --duration 60 -q
</code></pre>
<ul>
  <li><code>--duration &lt;seconds&gt;</code>：在指定秒数后优雅退出流。</li>
  <li><code>-q</code>：安静模式（减少非关键日志）。</li>
</ul>

<h3>本地密钥仓（SQLite）</h3>
<p>除明文 <code>.env</code> 外，可使用内置 SQLite 存储敏感配置。</p>

<pre><code class="language-bash"># 查看/确认数据库路径
python -m polymarket_analyzer --sqlite-path

# 将私钥写入本地数据库（请妥善保管机器与文件权限）
python -m polymarket_analyzer --sqlite-save pm_private_key "0xYourPrivateKeyHere"
</code></pre>

<hr>

<h2>⚙️ 环境变量</h2>

<p>应用启动时，<code>python-dotenv</code> 会从当前工作目录加载环境变量。</p>

<table>
  <thead>
    <tr>
      <th>变量名</th>
      <th>类型</th>
      <th>说明</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>PM_PRIVATE_KEY</code></td>
      <td><code>十六进制字符串</code></td>
      <td>CLOB 签名用私钥。<em>（别名：<code>POLYMARKET_PRIVATE_KEY</code>、<code>PRIVATE_KEY</code>）</em></td>
    </tr>
    <tr>
      <td><code>PM_SIG_TYPE</code></td>
      <td><code>整数</code></td>
      <td><code>0</code> = EOA（直连）<br> <code>1</code> = POLY_PROXY <br> <code>2</code> = Gnosis Safe</td>
    </tr>
    <tr>
      <td><code>PM_FUNDER</code></td>
      <td><code>地址</code></td>
      <td>可选。显式指定资金方 / 金库地址，用于保证金相关校验。</td>
    </tr>
    <tr>
      <td><code>PM_RPC_URL</code></td>
      <td><code>URL</code></td>
      <td>Polygon JSON-RPC，用于钱包与授权查询。</td>
    </tr>
    <tr>
      <td><code>PM_SIMULATE</code></td>
      <td><code>布尔</code></td>
      <td>为真（<code>1</code>、<code>true</code> 等）时跳过真实 <code>post_order</code>，仅在本地记录模拟下单。</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_KEY</code></td>
      <td><code>字符串</code></td>
      <td>Builder API Key（签名类型 1 / 2 的中继授权通常需要）。</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_SECRET</code></td>
      <td><code>字符串</code></td>
      <td>Builder API Secret。</td>
    </tr>
    <tr>
      <td><code>PM_BUILDER_PASSPHRASE</code></td>
      <td><code>字符串</code></td>
      <td>Builder API Passphrase。</td>
    </tr>
  </tbody>
</table>

<blockquote>
  <p><strong>安全提示：</strong>切勿将真实的 <code>.env</code> 或 <code>db/polymarket_analyzer.sqlite</code> 提交到版本库，并确保二者已列入 <code>.gitignore</code>。</p>
</blockquote>

<hr>

<h2>📂 代码结构</h2>

<p>仓库按 UI、核心执行与链上交互分层，便于维护与扩展。</p>

<pre><code>polymarket_analyzer/
├── __init__.py        # 包导出与延迟加载 GUI
├── __main__.py        # CLI：GUI、NDJSON 流、SQLite 配置
├── qt_main.py         # PyQt 主程序入口
├── core/              # 数据模型、Gamma、订单簿状态、WebSocket 会话
├── trading/           # 价差数学、CLOB 执行器、策略
├── infra/             # 环境映射与 SQLite 存储
├── chain/             # Web3（余额、Polygon RPC）
└── ui/                # PyQt 窗口、pyqtgraph、异步任务
</code></pre>

<hr>

<h2>📄 许可</h2>
<p><em>仓库未附带许可文件，默认保留所有权利。未经明确授权，请勿用于对外分发或生产环境。</em></p>
