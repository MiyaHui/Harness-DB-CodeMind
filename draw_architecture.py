import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
fm._load_fontmanager(try_read_cache=False)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

plt.rcParams['font.family'] = ['PingFang HK', 'STHeiti', 'Heiti TC', 'Songti SC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(48, 36), dpi=150)
ax.set_xlim(0, 48)
ax.set_ylim(0, 36)
ax.axis('off')
fig.patch.set_facecolor('#F8FAFC')

C = {
    'purple':      '#7C3AED',
    'purple_bg':   '#F5F3FF',
    'blue':        '#2563EB',
    'blue_bg':     '#EFF6FF',
    'cyan':        '#0891B2',
    'cyan_bg':     '#ECFEFF',
    'green':       '#059669',
    'green_bg':    '#ECFDF5',
    'amber':       '#D97706',
    'amber_bg':    '#FFFBEB',
    'red':         '#DC2626',
    'red_bg':      '#FEF2F2',
    'orange':      '#EA580C',
    'orange_bg':   '#FFF7ED',
    'dark':        '#0F172A',
    'mid':         '#475569',
    'light':       '#94A3B8',
    'border':      '#CBD5E1',
    'card':        '#FFFFFF',
    'bg':          '#F8FAFC',
}

def rbox(ax, x, y, w, h, fc, ec, lw=2.5, rad=0.4, zorder=3):
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0,rounding_size={rad}",
                         facecolor=fc, edgecolor=ec, linewidth=lw, zorder=zorder)
    ax.add_patch(box)

def card(ax, x, y, w, h, fc, ec, title='', title_color='', rad=0.4):
    rbox(ax, x, y, w, h, fc, ec, lw=3.0, rad=rad)
    if title:
        ax.text(x + w / 2, y + h - 0.5, title,
                ha='center', va='top', fontsize=30, fontweight='bold',
                color=title_color or ec, zorder=5)

def chip(ax, x, y, w, h, fc, ec, text, tc=None, fs=25, rad=0.3):
    rbox(ax, x, y, w, h, fc, ec, lw=2.0, rad=rad, zorder=4)
    ax.text(x + w / 2, y + h / 2, text,
            ha='center', va='center', fontsize=fs, fontweight='semibold',
            color=tc or ec, zorder=5)

def arrow(ax, x1, y1, x2, y2, color='#94A3B8', lw=3.0, style='->'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw),
                zorder=2)

def dashed(ax, x1, y1, x2, y2, color='#94A3B8', lw=2.5):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw, linestyle=(0, (5, 3))),
                zorder=2)

# ════════════════════════════════════════════════════════════════
# TITLE
# ════════════════════════════════════════════════════════════════
ax.text(24, 34.8, 'Harness-DB-CodeMind', ha='center', va='center',
        fontsize=84, fontweight='bold', color=C['dark'], zorder=10)
ax.text(24, 33.5, 'Enterprise AI Code Intelligence Infrastructure',
        ha='center', va='center', fontsize=42, color=C['mid'], zorder=10)
ax.plot([6, 42], [32.8, 32.8], color=C['border'], lw=2.0, zorder=2)

# ════════════════════════════════════════════════════════════════
# LAYER 1 — APPLICATION LAYER
# ════════════════════════════════════════════════════════════════
L1y = 28.0
L1h = 4.0
card(ax, 2, L1y, 44, L1h, C['purple_bg'], C['purple'],
     title='APPLICATION  LAYER', title_color=C['purple'], rad=0.5)

apps = [
    ('Architecture QA', '架构问答'),
    ('Impact Analysis', '影响分析'),
    ('Risk Assessment', '风险评估'),
    ('Data Lineage', '数据血缘'),
    ('Refactor Suggest', '重构建议'),
]
aw, ah, ag = 7.5, 1.5, 0.8
atw = len(apps) * aw + (len(apps) - 1) * ag
asx = (48 - atw) / 2
for i, (en, zh) in enumerate(apps):
    x = asx + i * (aw + ag)
    chip(ax, x, L1y + 0.8, aw, ah, C['card'], C['purple'], en, C['purple'], fs=26)
    ax.text(x + aw / 2, L1y + 0.5, zh, ha='center', va='center',
            fontsize=20, color=C['light'], zorder=5)

# ════════════════════════════════════════════════════════════════
# LAYER 2 — HARNESS ORCHESTRATOR
# ════════════════════════════════════════════════════════════════
L2y = 18.0
L2h = 9.0
card(ax, 2, L2y, 44, L2h, C['blue_bg'], C['blue'],
     title='HARNESS  ORCHESTRATOR', title_color=C['blue'], rad=0.5)

# Core orchestrator box
rbox(ax, 16, L2y + 0.5, 16, 2.0, C['blue'], C['blue'], lw=2.5, rad=0.35)
ax.text(24, L2y + 1.5, 'Orchestrator  Core', ha='center', va='center',
        fontsize=36, fontweight='bold', color='#FFFFFF', zorder=5)

# Agents row 1
a1 = [
    ('Query Parser', '查询解析', C['cyan']),
    ('Graph Retrieval', '图检索', C['cyan']),
    ('Impact Analysis', '影响传播', C['cyan']),
    ('Risk Scoring', '风险评分', C['cyan']),
]
cw, ch, cg = 9.5, 1.6, 0.7
ctw = len(a1) * cw + (len(a1) - 1) * cg
csx = (48 - ctw) / 2
for i, (en, zh, col) in enumerate(a1):
    x = csx + i * (cw + cg)
    chip(ax, x, L2y + 6.5, cw, ch, C['card'], col, en, col, fs=26)
    ax.text(x + cw / 2, L2y + 6.2, zh, ha='center', va='center',
            fontsize=18, color=C['light'], zorder=5)

# Agents row 2
a2 = [
    ('Graph Builder', '图构建 (离线)', C['green']),
    ('Lineage Builder', '血缘构建 (离线)', C['green']),
    ('LLM Reasoning', '语义解释 (可选)', C['purple']),
    ('Budget Controller', '成本控制', C['orange']),
]
for i, (en, zh, col) in enumerate(a2):
    x = csx + i * (cw + cg)
    chip(ax, x, L2y + 4.0, cw, ch, C['card'], col, en, col, fs=26)
    ax.text(x + cw / 2, L2y + 3.7, zh, ha='center', va='center',
            fontsize=18, color=C['light'], zorder=5)

# Agent type labels
ax.text(csx + 2 * cw + cg + cw / 2, L2y + 8.2, 'ONLINE AGENTS',
        ha='center', va='center', fontsize=20, color=C['cyan'],
        fontweight='bold', fontstyle='italic', zorder=5)
ax.text(csx + 2 * cw + cg + cw / 2, L2y + 5.7, 'OFFLINE / OPTIONAL',
        ha='center', va='center', fontsize=20, color=C['green'],
        fontweight='bold', fontstyle='italic', zorder=5)

# Arrows within orchestrator
arrow(ax, 24, L2y + 2.5, 24, L2y + 4.0, C['blue'], 3.0)
arrow(ax, 24, L2y + 5.6, 24, L2y + 6.5, C['blue'], 2.5)

# ════════════════════════════════════════════════════════════════
# LAYER 3 — HYBRID KNOWLEDGE LAYER
# ════════════════════════════════════════════════════════════════
L3y = 10.0
L3h = 7.0
card(ax, 2, L3y, 21.5, L3h, C['amber_bg'], C['amber'],
     title='HYBRID  KNOWLEDGE  LAYER', title_color=C['amber'], rad=0.5)

kitems = [
    ('Code Property Graph', 'CPG 代码属性图'),
    ('Data Lineage Graph', '数据血缘图'),
    ('Runtime Trace Graph', '运行时追踪图'),
    ('Business Ontology', '业务本体'),
    ('Embedding Index', 'FAISS 向量索引'),
    ('Neo4j Graph Store', '图数据库存储'),
]
kw, kh, kgx, kgy = 6.0, 1.5, 0.6, 0.6
ksx = 3.5
ksy = L3y + 0.8
for i, (en, zh) in enumerate(kitems):
    row = i // 3
    col = i % 3
    kx = ksx + col * (kw + kgx)
    ky = ksy + (1 - row) * (kh + kgy)
    chip(ax, kx, ky, kw, kh, C['card'], C['amber'], en, C['amber'], fs=22)
    ax.text(kx + kw / 2, ky - 0.25, zh, ha='center', va='center',
            fontsize=16, color=C['light'], zorder=5)

# ════════════════════════════════════════════════════════════════
# LAYER 4 — DETERMINISTIC LAYER
# ════════════════════════════════════════════════════════════════
L4y = 10.0
L4h = 7.0
card(ax, 24.5, L4y, 21.5, L4h, C['red_bg'], C['red'],
     title='DETERMINISTIC  LAYER', title_color=C['red'], rad=0.5)

ditems = [
    ('SQL AST Parser', 'SQL 语法解析'),
    ('CPG Builder', '多语言 CPG 构建'),
    ('Program Slicer', '程序切片'),
    ('Git Analyzer', '变更分析'),
    ('Call Graph', '调用图提取'),
    ('Column Lineage', '列级血缘追踪'),
]
dsx = 26.0
dsy = L4y + 0.8
for i, (en, zh) in enumerate(ditems):
    row = i // 3
    col = i % 3
    dx = dsx + col * (kw + kgx)
    dy = dsy + (1 - row) * (kh + kgy)
    chip(ax, dx, dy, kw, kh, C['card'], C['red'], en, C['red'], fs=22)
    ax.text(dx + kw / 2, dy - 0.25, zh, ha='center', va='center',
            fontsize=16, color=C['light'], zorder=5)

# ════════════════════════════════════════════════════════════════
# LAYER 5 — PRINCIPLES & DATA FLOW
# ════════════════════════════════════════════════════════════════
L5y = 1.0
L5h = 8.0
card(ax, 2, L5y, 44, L5h, '#F1F5F9', C['border'],
     title='CORE  PRINCIPLES  &  DATA  FLOW', title_color=C['mid'], rad=0.5)

# Data flow pipeline
steps = [
    ('User Query', '用户查询', C['purple']),
    ('Parse Intent', '意图解析', C['blue']),
    ('Graph Retrieval', '图检索', C['cyan']),
    ('Impact Analysis', '影响传播', C['amber']),
    ('Risk Scoring', '风险评分', C['red']),
    ('LLM Explain', 'LLM 解释', C['purple']),
    ('Response', '返回结果', C['green']),
]
sw, sh, sg = 5.2, 1.5, 1.0
stw = len(steps) * sw + (len(steps) - 1) * sg
ssx = (48 - stw) / 2
ssy = L5y + 5.5
for i, (en, zh, col) in enumerate(steps):
    x = ssx + i * (sw + sg)
    chip(ax, x, ssy, sw, sh, C['card'], col, en, col, fs=24)
    ax.text(x + sw / 2, ssy - 0.3, zh, ha='center', va='center',
            fontsize=18, color=C['light'], zorder=5)
    if i < len(steps) - 1:
        arrow(ax, x + sw + 0.15, ssy + sh / 2,
              x + sw + sg - 0.15, ssy + sh / 2,
              C['light'], 2.5)

# Principles
prins = [
    ('Code as Graph', '代码即图谱\nCPG + Lineage + Call Graph', C['blue']),
    ('Neuro-Symbolic', '神经符号架构\nDeterministic + LLM', C['purple']),
    ('Token Budget', 'Token 预算控制\n可预测 · 可降级', C['orange']),
    ('Harness 3-Layer', '三层控制\n解析 → 检索 → 推理', C['green']),
]
pw, ph, pg = 9.5, 2.8, 1.0
ptw = len(prins) * pw + (len(prins) - 1) * pg
psx = (48 - ptw) / 2
psy = L5y + 0.8
for i, (title, desc, col) in enumerate(prins):
    x = psx + i * (pw + pg)
    rbox(ax, x, psy, pw, ph, C['card'], col, lw=3.0, rad=0.35)
    ax.text(x + pw / 2, psy + ph - 0.4, title,
            ha='center', va='top', fontsize=28, fontweight='bold',
            color=col, zorder=5)
    ax.text(x + pw / 2, psy + ph - 1.0, desc,
            ha='center', va='top', fontsize=20, color=C['mid'],
            zorder=5, linespacing=1.5)

# ════════════════════════════════════════════════════════════════
# INTER-LAYER ARROWS
# ════════════════════════════════════════════════════════════════
# App → Orchestrator
arrow(ax, 24, L1y, 24, L2y + L2h, C['purple'], 4.0)
# Orchestrator → Knowledge
arrow(ax, 12, L2y, 12, L3y + L3h, C['blue'], 3.0)
# Orchestrator → Deterministic
arrow(ax, 36, L2y, 36, L4y + L4h, C['blue'], 3.0)
# Knowledge ↔ Deterministic
dashed(ax, 23.5, L3y + L3h / 2, 24.5, L4y + L4h / 2, C['light'], 2.5)

# Layer number badges
badges = [
    (0.5, L1y + L1h - 0.1, 'L1', C['purple']),
    (0.5, L2y + L2h - 0.1, 'L2', C['blue']),
    (0.5, L3y + L3h - 0.1, 'L3', C['amber']),
    (24.0, L4y + L4h - 0.1, 'L4', C['red']),
    (0.5, L5y + L5h - 0.1, 'L5', C['mid']),
]
for bx, by, bt, bc in badges:
    rbox(ax, bx, by - 0.7, 1.0, 0.7, bc, bc, lw=0, rad=0.2)
    ax.text(bx + 0.5, by - 0.35, bt, ha='center', va='center',
            fontsize=22, fontweight='bold', color='#FFFFFF', zorder=6)

# ════════════════════════════════════════════════════════════════
# SAVE
# ════════════════════════════════════════════════════════════════
plt.tight_layout(pad=0.5)
plt.savefig('/Users/miya/Documents/trae_projects/Harness-DB-CodeMind/architecture.png',
            dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor(),
            edgecolor='none')
plt.close()
print("Done! Saved to architecture.png")
