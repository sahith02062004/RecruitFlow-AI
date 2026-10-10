import os
import matplotlib.pyplot as plt
import numpy as np

os.makedirs(r"C:\Users\sahit\.gemini\antigravity\scratch\recruitflow-ai\presentation_assets", exist_ok=True)
asset_dir = r"C:\Users\sahit\.gemini\antigravity\scratch\recruitflow-ai\presentation_assets"

# 1. Image 1: Dual-Score Architecture Gauge / Comparison
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=200)
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#f8fafc')

categories = ['ATS Quality\nScore A\n(Readability)', 'Job Match\nScore B\n(Fitness)']
scores = [88, 92]
colors = ['#0f766e', '#1e3a8a']

bars = ax.bar(categories, scores, color=colors, width=0.45, edgecolor='#0f172a', linewidth=1.5)
ax.set_ylim(0, 115)
ax.set_ylabel('Score (0 - 100)', fontsize=12, fontweight='bold', color='#0f172a')
ax.set_title('Dual-Score Separation Architecture', fontsize=14, fontweight='bold', color='#0f172a', pad=15)

for bar in bars:
    yval = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2.0, yval + 3, f"{int(yval)}%", ha='center', va='bottom', fontsize=14, fontweight='bold', color='#0f172a')

ax.axhline(75, color='#e11d48', linestyle='--', linewidth=1.5, label='High Fitness Threshold (75%)')
ax.legend(loc='upper right', frameon=True, facecolor='#ffffff', edgecolor='#cbd5e1')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#cbd5e1')
ax.spines['bottom'].set_color('#cbd5e1')
plt.tight_layout()
plt.savefig(os.path.join(asset_dir, "dual_score_chart.png"))
plt.close()

# 2. Image 2: ATS Quality Breakdown (7 Categories Pie / Donut Chart)
fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=200)
fig.patch.set_facecolor('#ffffff')

labels = [
    'Exp. Formatting (20%)',
    'Contact Links (15%)',
    'Education (15%)',
    'Skills Section (15%)',
    'Action Verbs (15%)',
    'Achievements (10%)',
    'Readability (10%)'
]
sizes = [20, 15, 15, 15, 15, 10, 10]
colors = ['#1e3a8a', '#0284c7', '#0f766e', '#0d9488', '#14b8a6', '#6366f1', '#8b5cf6']

wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=140, 
                                  colors=colors, wedgeprops=dict(width=0.4, edgecolor='#ffffff', linewidth=2),
                                  pctdistance=0.75)
for t in texts:
    t.set_fontsize(9)
    t.set_color('#0f172a')
    t.set_fontweight('bold')
for at in autotexts:
    at.set_fontsize(10)
    at.set_color('#ffffff')
    at.set_fontweight('bold')

ax.set_title('7-Category ATS Quality Matrix (100% Total)', fontsize=13, fontweight='bold', color='#0f172a', pad=10)
plt.tight_layout()
plt.savefig(os.path.join(asset_dir, "ats_categories_pie.png"))
plt.close()

# 3. Image 3: Recruitment Hiring Funnel (Funnel Bar Chart)
fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=200)
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#f8fafc')

stages = ['Submitted', 'Under Review', 'Shortlisted', 'Interviewed', 'Offered', 'Hired']
counts = [100, 68, 38, 22, 10, 8]
stage_colors = ['#94a3b8', '#60a5fa', '#3b82f6', '#0284c7', '#0f766e', '#16a34a']

bars = ax.barh(stages[::-1], counts[::-1], color=stage_colors[::-1], height=0.55, edgecolor='#0f172a', linewidth=1.2)
ax.set_xlim(0, 120)
ax.set_xlabel('Candidate Volume & Conversion', fontsize=11, fontweight='bold', color='#0f172a')
ax.set_title('Recruitment Pipeline Hiring Funnel', fontsize=14, fontweight='bold', color='#0f172a', pad=12)

for bar in bars:
    w = bar.get_width()
    ax.text(w + 2, bar.get_y() + bar.get_height()/2.0, f"{int(w)} ({w}%)", ha='left', va='center', fontsize=10, fontweight='bold', color='#0f172a')

ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#cbd5e1')
ax.spines['bottom'].set_color('#cbd5e1')
plt.tight_layout()
plt.savefig(os.path.join(asset_dir, "hiring_funnel_chart.png"))
plt.close()

# 4. Image 4: Pytest 85/85 Test Pass Summary
fig, ax = plt.subplots(figsize=(6, 4.5), dpi=200)
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#f8fafc')

suites = ['Auth', 'Basic', 'Interviews', 'Jobs/Apps', 'Matching', 'Modules', 'Phase 7 ATS', 'Profiles', 'RBAC', 'Resumes']
counts = [7, 5, 14, 7, 15, 2, 14, 3, 6, 12]

y_pos = np.arange(len(suites))
bars = ax.barh(y_pos, counts, color='#16a34a', height=0.6, edgecolor='#14532d', linewidth=1)
ax.set_yticks(y_pos)
ax.set_yticklabels(suites, fontsize=9, fontweight='bold', color='#0f172a')
ax.invert_yaxis()
ax.set_xlabel('Tests Passed (Total = 85, 0 Failed)', fontsize=11, fontweight='bold', color='#0f172a')
ax.set_title('Automated Test Suite Verification (100% Pass)', fontsize=13, fontweight='bold', color='#0f172a', pad=12)

for bar in bars:
    w = bar.get_width()
    ax.text(w + 0.3, bar.get_y() + bar.get_height()/2.0, f"{int(w)} ✓", ha='left', va='center', fontsize=9, fontweight='bold', color='#16a34a')

ax.set_xlim(0, 18)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color('#cbd5e1')
ax.spines['bottom'].set_color('#cbd5e1')
plt.tight_layout()
plt.savefig(os.path.join(asset_dir, "test_suite_chart.png"))
plt.close()

# 5. Image 5: System Architecture Flow Diagram
fig, ax = plt.subplots(figsize=(7, 4.5), dpi=200)
fig.patch.set_facecolor('#ffffff')
ax.set_facecolor('#f8fafc')
ax.axis('off')

boxes = [
    (0.08, 0.65, 0.38, 0.25, 'Candidate Portal\n• PDF/DOCX Resume Upload\n• Magic-Byte Inspection\n• ATS Quality Feedback', '#e0f2fe', '#0284c7'),
    (0.54, 0.65, 0.38, 0.25, 'Recruiter Workspace\n• Requisition Lifecycle\n• Kanban Pipeline\n• Interview Rubrics', '#f0fdf4', '#16a34a'),
    (0.08, 0.20, 0.38, 0.30, 'Document Parser Engine\n• PyMuPDF & docx extract\n• 80+ Canonical Skills\n• Scanned PDF Diagnostics', '#fef3c7', '#d97706'),
    (0.54, 0.20, 0.38, 0.30, 'Deterministic AI Matcher\n• Category Weight Formula\n• Dynamic Redistribution\n• Evidence Coverage', '#ede9fe', '#7c3aed')
]

for x, y, w, h, text, bg, border in boxes:
    rect = plt.Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=2, transform=ax.transAxes, zorder=2)
    ax.add_patch(rect)
    ax.text(x + w/2, y + h/2, text, transform=ax.transAxes, ha='center', va='center', fontsize=9.5, fontweight='bold', color='#0f172a', zorder=3)

# Connectors
ax.annotate('', xy=(0.52, 0.77), xytext=(0.48, 0.77), arrowprops=dict(arrowstyle="<->", color="#64748b", lw=2))
ax.annotate('', xy=(0.27, 0.52), xytext=(0.27, 0.63), arrowprops=dict(arrowstyle="->", color="#64748b", lw=2))
ax.annotate('', xy=(0.73, 0.52), xytext=(0.73, 0.63), arrowprops=dict(arrowstyle="->", color="#64748b", lw=2))
ax.annotate('', xy=(0.52, 0.35), xytext=(0.48, 0.35), arrowprops=dict(arrowstyle="<->", color="#64748b", lw=2))

ax.set_title('RecruitFlow AI System Architecture Flow', fontsize=14, fontweight='bold', color='#0f172a', pad=15)
plt.tight_layout()
plt.savefig(os.path.join(asset_dir, "architecture_flow.png"))
plt.close()

print("All presentation images generated successfully.")
