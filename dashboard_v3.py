# -*- coding: utf-8 -*-
"""
dashboard_v3.py — ESG 그린워싱 모니터링 대시보드 (한글 전문가 평가용)
실행: streamlit run dashboard_v3.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="ESG 그린워싱 모니터", layout="wide")

# ── 비밀번호 보호 ──
def check_password():
    """Streamlit Cloud Secrets 기반 비밀번호 확인"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown(
        '<div style="max-width:420px; margin:15vh auto; text-align:center;">'
        '<h2>ESG 그린워싱 모니터링 대시보드</h2>'
        '<p style="color:#666;">접근 권한이 필요합니다. 안내받은 비밀번호를 입력해 주세요.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_left, col_mid, col_right = st.columns([1, 2, 1])
    with col_mid:
        pwd = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")
        if st.button("확인", use_container_width=True):
            if pwd == st.secrets["password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    return False

if not check_password():
    st.stop()

# ── 데이터 로드 (실명) ──
@st.cache_data
def load_data():
    import warnings
    warnings.filterwarnings("ignore")
    df = pd.read_excel(Path("./output/di_all60_finbert.xlsx"),
                       sheet_name="DI_전체데이터", header=1)
    cols = [
        "기업명","산업군","연도","분기",
        "KCGS_종합","KCGS_E","KCGS_S","KCGS_G",
        "KCGS_종합_mean","KCGS_종합_std","KCGS_E_mean","KCGS_E_std",
        "KCGS_S_mean","KCGS_S_std","KCGS_G_mean","KCGS_G_std",
        "Z_KCGS_종합","Z_KCGS_E","Z_KCGS_S","Z_KCGS_G",
        "BK_감성","BK_긍정수","BK_부정수","BK_중립수","BK_총건수",
        "JP_종합","JP_급여복지","JP_워라밸","JP_사내문화","JP_비전","JP_경영진","JP_n",
        "JP_S","JP_G","Z_BK","Z_JP","Z_JP_S","Z_JP_G",
        "DI_ext","DI_int","DI_gap","DI_int_S","DI_int_G","ERDP_유형",
    ]
    df.columns = cols
    for c in cols:
        if c not in {"기업명","산업군","분기","ERDP_유형"}:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    vol_path = Path("./output/stock_volatility_quarterly.csv")
    if vol_path.exists():
        df_vol = pd.read_csv(vol_path)
        df = df.merge(df_vol[["기업명","분기","변동성_연율화","누적수익률"]],
                      on=["기업명","분기"], how="left")
    return df

df = load_data()

TYPE_INFO = {
    "A. 총체적과장형": {"icon": "[A]", "color": "#EF5350", "label": "총체적과장형", "desc": "외부 공시와 내부 평판 모두 실제보다 과장 (그린워싱 위험 높음)", "risk": 5},
    "B. 외부미화형":   {"icon": "[B]", "color": "#FF8A65", "label": "외부미화형", "desc": "미디어 평판은 부정적이나 직원 인식은 긍정적", "risk": 4},
    "C. 내부은폐형":   {"icon": "[C]", "color": "#FFA726", "label": "내부은폐형", "desc": "미디어 평판은 긍정적이나 직원은 부정적으로 인식", "risk": 3},
    "D. 균형일치형":   {"icon": "[D]", "color": "#66BB6A", "label": "균형일치형", "desc": "공시와 실제 인식이 대체로 일치 (양호)", "risk": 1},
    "E. 총체적과소형": {"icon": "[E]", "color": "#42A5F5", "label": "총체적과소형", "desc": "실제 성과가 공시보다 우수 (보수적 공시)", "risk": 2},
    "F. ESG미성숙":   {"icon": "[F]", "color": "#9E9E9E", "label": "ESG미성숙", "desc": "ESG 공시 수준이 매우 낮아 비교 불가", "risk": 0},
    "N/A":           {"icon": "[-]", "color": "#E0E0E0", "label": "N/A", "desc": "분석 데이터 부족", "risk": 0},
}

KCGS_GRADE = {8: "A+", 6: "A", 4: "B+", 2: "B", 1: "C", 0: "D"}

IND_KR = {
    "Energy & Materials": "에너지/소재",
    "Consumer & Retail": "소비재/유통",
    "Finance": "금융",
    "Healthcare & Bio": "헬스케어/바이오",
    "Industrials": "산업재",
    "Technology": "기술",
}

# ── 사이드바 ──
with st.sidebar:
    st.markdown(
        '<div style="text-align:center; background:linear-gradient(135deg,#1B5E20,#2E7D32); '
        'padding:25px 10px; border-radius:12px; margin-bottom:10px;">'
        '<h1 style="color:white; margin:5px 0; font-size:24px;">'
        'ESG 그린워싱<br>모니터링 대시보드</h1>'
        '<p style="color:#A5D6A7; font-size:13px; margin:5px 0 0 0;">KOSPI 60개 기업 | 2023~2025</p>'
        '</div>',
        unsafe_allow_html=True
    )
    st.divider()

    industries = ["전체"] + sorted(df["산업군"].unique())
    sel_ind = st.selectbox("산업군 선택", industries)
    corps = sorted(df[df["산업군"] == sel_ind]["기업명"].unique()) if sel_ind != "전체" else sorted(df["기업명"].unique())
    sel_corp = st.selectbox("기업 선택", corps)

    st.divider()
    st.markdown("**ERDP 유형 범례**")
    for t, info in TYPE_INFO.items():
        if t != "N/A":
            st.markdown(f"**{info['icon']} {info['label']}** - {info['desc'][:20]}...")

# ── 기업 데이터 ──
cd = df[df["기업명"] == sel_corp].sort_values("분기").reset_index(drop=True)
industry = cd["산업군"].iloc[0]
ind_kr = IND_KR.get(industry, industry)
latest_valid = cd[~cd["ERDP_유형"].isin(["N/A"])].iloc[-1] if len(cd[~cd["ERDP_유형"].isin(["N/A"])]) > 0 else None

# ═══════════════════════════════════════════════════
# 헤더
# ═══════════════════════════════════════════════════
if latest_valid is not None:
    etype = latest_valid["ERDP_유형"]
    info = TYPE_INFO.get(etype, TYPE_INFO["N/A"])

    st.markdown(f"# {info['icon']} {sel_corp}")
    q_label = latest_valid['분기']
    st.markdown(f"### {ind_kr} ({industry}) | 최신 분기: **:blue[{q_label}]**")

    risk = info["risk"]
    if risk >= 4:
        st.markdown(
            f'<div style="background:#FFCDD2; border-left:8px solid #C62828; padding:20px; '
            f'border-radius:8px; margin:10px 0;">'
            f'<h2 style="color:#C62828; margin:0;">그린워싱 경고</h2>'
            f'<p style="font-size:18px; margin:8px 0 0 0;"><b>{info["label"]}</b> - {info["desc"]}</p>'
            f'<p style="font-size:14px; color:#555; margin:4px 0 0 0;">'
            f'ESG 공시가 실제 평판보다 과장되었을 가능성이 높습니다. 즉각적인 점검이 필요합니다.</p></div>',
            unsafe_allow_html=True
        )
    elif risk == 3:
        st.markdown(
            f'<div style="background:#FFF3E0; border-left:8px solid #E65100; padding:20px; '
            f'border-radius:8px; margin:10px 0;">'
            f'<h2 style="color:#E65100; margin:0;">주의 필요</h2>'
            f'<p style="font-size:18px; margin:8px 0 0 0;"><b>{info["label"]}</b> - {info["desc"]}</p></div>',
            unsafe_allow_html=True
        )
    elif risk <= 1:
        st.markdown(
            f'<div style="background:#E8F5E9; border-left:8px solid #2E7D32; padding:20px; '
            f'border-radius:8px; margin:10px 0;">'
            f'<h2 style="color:#2E7D32; margin:0;">양호</h2>'
            f'<p style="font-size:18px; margin:8px 0 0 0;"><b>{info["label"]}</b> - {info["desc"]}</p></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div style="background:#E3F2FD; border-left:8px solid #1565C0; padding:20px; '
            f'border-radius:8px; margin:10px 0;">'
            f'<h2 style="color:#1565C0; margin:0;">보수적 공시</h2>'
            f'<p style="font-size:18px; margin:8px 0 0 0;"><b>{info["label"]}</b> - {info["desc"]}</p></div>',
            unsafe_allow_html=True
        )
else:
    st.markdown(f"# {sel_corp}")
    st.warning("분석 가능한 데이터가 부족합니다")

st.divider()

# ═══════════════════════════════════════════════════
# 1행: 핵심 지표 4개
# ═══════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4)

CARD_CSS = """
<div style="background:#FAFAFA; border:1px solid #E0E0E0; border-radius:10px;
            padding:18px; min-height:200px; text-align:center;">
<p style="font-size:20px; color:#333; font-weight:bold; letter-spacing:1px;
          margin:0 0 15px 0; border-bottom:2px solid #1B5E20; padding-bottom:8px;">{title}</p>
{content}
</div>
"""

with c1:
    if latest_valid is not None and pd.notna(latest_valid["BK_감성"]):
        bk = latest_valid["BK_감성"]
        if bk > 0.2:
            val_text = f'<p style="font-size:32px; font-weight:bold; color:#2E7D32; margin:0;">긍정적 ({bk:+.2f})</p>'
        elif bk < -0.2:
            val_text = f'<p style="font-size:32px; font-weight:bold; color:#C62828; margin:0;">부정적 ({bk:+.2f})</p>'
        else:
            val_text = f'<p style="font-size:32px; font-weight:bold; color:#F57F17; margin:0;">중립 ({bk:+.2f})</p>'
        pos = int(latest_valid["BK_긍정수"]) if pd.notna(latest_valid["BK_긍정수"]) else 0
        neg = int(latest_valid["BK_부정수"]) if pd.notna(latest_valid["BK_부정수"]) else 0
        neu = int(latest_valid["BK_중립수"]) if pd.notna(latest_valid["BK_중립수"]) else 0
        total = pos + neg + neu
        val_text += f'<p style="font-size:12px; color:#999; margin:8px 0 0 0;">긍정 {pos} / 부정 {neg} / 중립 {neu} (총 {total}건)</p>'
    else:
        val_text = '<p style="font-size:24px; color:#999; margin:0;">데이터 없음</p>'
    st.markdown(CARD_CSS.format(title="미디어 평판", content=val_text), unsafe_allow_html=True)

with c2:
    if latest_valid is not None and pd.notna(latest_valid["JP_종합"]):
        jp = latest_valid["JP_종합"]
        val_text = f'<p style="font-size:36px; font-weight:bold; margin:0;">{jp:.1f} / 5.0</p>'
        val_text += '<p style="font-size:12px; color:#999; margin:8px 0 0 0;">잡플래닛 종합평점</p>'
    else:
        val_text = '<p style="font-size:24px; color:#999; margin:0;">데이터 없음</p>'
    st.markdown(CARD_CSS.format(title="직원 만족도", content=val_text), unsafe_allow_html=True)

with c3:
    if latest_valid is not None:
        kcgs = latest_valid["KCGS_종합"]
        grade = KCGS_GRADE.get(int(kcgs), "?") if pd.notna(kcgs) else "?"
        e_g = KCGS_GRADE.get(int(latest_valid["KCGS_E"]), "?") if pd.notna(latest_valid["KCGS_E"]) else "?"
        s_g = KCGS_GRADE.get(int(latest_valid["KCGS_S"]), "?") if pd.notna(latest_valid["KCGS_S"]) else "?"
        g_g = KCGS_GRADE.get(int(latest_valid["KCGS_G"]), "?") if pd.notna(latest_valid["KCGS_G"]) else "?"
        val_text = f'<p style="font-size:36px; font-weight:bold; margin:0;">{grade} 등급</p>'
        val_text += f'<p style="font-size:13px; color:#666; margin:8px 0 0 0;">환경: <b>{e_g}</b> | 사회: <b>{s_g}</b> | 지배구조: <b>{g_g}</b></p>'
    else:
        val_text = '<p style="font-size:24px; color:#999; margin:0;">데이터 없음</p>'
    st.markdown(CARD_CSS.format(title="ESG 공시 등급 (KCGS)", content=val_text), unsafe_allow_html=True)

with c4:
    if latest_valid is not None and "변동성_연율화" in latest_valid.index and pd.notna(latest_valid.get("변동성_연율화")):
        vol = latest_valid["변동성_연율화"]
        vol_pct = vol * 100
        if vol > 0.5:
            color, level, desc = "#C62828", "높음", "매우 불안정"
        elif vol > 0.35:
            color, level, desc = "#E65100", "보통", "보통 수준"
        else:
            color, level, desc = "#2E7D32", "낮음", "안정적"
        val_text = f'<p style="font-size:36px; font-weight:bold; color:{color}; margin:0;">{level} {vol_pct:.1f}%</p>'
        val_text += f'<p style="font-size:13px; color:#666; margin:8px 0 0 0;">{desc} (1년간 약 +-{vol_pct:.0f}% 등락 가능)</p>'
        ind_avg_vol = df[df["산업군"] == industry]["변동성_연율화"].mean()
        diff = vol_pct - ind_avg_vol * 100
        if diff > 5:
            val_text += f'<p style="font-size:11px; color:#999; margin:4px 0 0 0;">산업 평균({ind_avg_vol*100:.1f}%)보다 {diff:.1f}%p 높음</p>'
        elif diff < -5:
            val_text += f'<p style="font-size:11px; color:#999; margin:4px 0 0 0;">산업 평균({ind_avg_vol*100:.1f}%)보다 {abs(diff):.1f}%p 낮음</p>'
        else:
            val_text += f'<p style="font-size:11px; color:#999; margin:4px 0 0 0;">산업 평균({ind_avg_vol*100:.1f}%)과 비슷한 수준</p>'
    else:
        val_text = '<p style="font-size:24px; color:#999; margin:0;">데이터 없음</p>'
    st.markdown(CARD_CSS.format(title="주가 변동성", content=val_text), unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════
# 2행: 괴리 진단 게이지 + 타임라인
# ═══════════════════════════════════════════════════
col_a, col_b = st.columns([1, 2])

with col_a:
    st.markdown("### 괴리 진단")
    if latest_valid is not None:
        di_ext = latest_valid["DI_ext"] if pd.notna(latest_valid["DI_ext"]) else 0
        di_int = latest_valid["DI_int"] if pd.notna(latest_valid["DI_int"]) else 0

        fig_g1 = go.Figure(go.Indicator(
            mode="gauge+number", value=round(di_ext, 1),
            number={"font": {"size": 36}, "valueformat": "+.1f"},
            gauge=dict(
                axis=dict(range=[-3, 3], tickvals=[-3, -1, 0, 1, 3], tickfont=dict(size=11)),
                bar=dict(color="darkblue"),
                steps=[dict(range=[-3, -0.3], color="#FFCDD2"),
                       dict(range=[-0.3, 0.3], color="#C8E6C9"),
                       dict(range=[0.3, 3], color="#BBDEFB")],
                threshold=dict(line=dict(color="red", width=3), thickness=0.8, value=di_ext),
            ),
        ))
        fig_g1.update_layout(height=200, margin=dict(t=30, b=0, l=30, r=30))
        st.markdown("**DI_ext (시장 괴리: 미디어 vs 공시)**")
        st.plotly_chart(fig_g1, use_container_width=True)

        fig_g2 = go.Figure(go.Indicator(
            mode="gauge+number", value=round(di_int, 1),
            number={"font": {"size": 36}, "valueformat": "+.1f"},
            gauge=dict(
                axis=dict(range=[-3, 3], tickvals=[-3, -1, 0, 1, 3], tickfont=dict(size=11)),
                bar=dict(color="darkblue"),
                steps=[dict(range=[-3, -0.3], color="#FFCDD2"),
                       dict(range=[-0.3, 0.3], color="#C8E6C9"),
                       dict(range=[0.3, 3], color="#BBDEFB")],
                threshold=dict(line=dict(color="red", width=3), thickness=0.8, value=di_int),
            ),
        ))
        fig_g2.update_layout(height=200, margin=dict(t=30, b=0, l=30, r=30))
        st.markdown("**DI_int (조직 괴리: 직원 vs 공시)**")
        st.plotly_chart(fig_g2, use_container_width=True)
        st.caption("빨간 영역 = 과장공시 (그린워싱) | 초록 영역 = 균형 | 파란 영역 = 보수적 공시")

with col_b:
    st.markdown("### 분기별 ESG 공시 건전성 변화")
    st.caption("각 분기마다 이 기업의 ESG 공시 상태를 신호등처럼 보여줍니다.")
    st.markdown(
        ':red[**빨강 = 위험 (과장공시)**] | '
        ':orange[**주황 = 주의**] | '
        ':green[**초록 = 양호**] | '
        ':blue[**파랑 = 보수적 공시**]'
    )

    timeline = cd[cd["ERDP_유형"] != "N/A"].copy()
    if len(timeline) > 0:
        fig_tl = go.Figure()
        all_q = cd["분기"].tolist()
        all_di_ext = cd.set_index("분기")["DI_ext"].reindex(all_q).interpolate().tolist()
        all_di_int = cd.set_index("분기")["DI_int"].reindex(all_q).interpolate().tolist()

        fig_tl.add_trace(go.Scatter(x=all_q, y=all_di_ext, mode="lines",
            line=dict(color="#C62828", width=3), showlegend=True, hoverinfo="skip",
            name="DI_ext (미디어 vs 공시)"))
        valid_ext = timeline.dropna(subset=["DI_ext"])
        if len(valid_ext) > 0:
            fig_tl.add_trace(go.Scatter(x=valid_ext["분기"], y=valid_ext["DI_ext"],
                mode="markers", marker=dict(size=8, color="#C62828", symbol="circle"),
                showlegend=False, hovertemplate="DI_ext: %{y:+.2f}<extra></extra>"))

        fig_tl.add_trace(go.Scatter(x=all_q, y=all_di_int, mode="lines",
            line=dict(color="#1565C0", width=3, dash="dot"), showlegend=True, hoverinfo="skip",
            name="DI_int (직원 vs 공시)"))
        valid_int = cd.dropna(subset=["DI_int"])
        if len(valid_int) > 0:
            fig_tl.add_trace(go.Scatter(x=valid_int["분기"], y=valid_int["DI_int"],
                mode="markers", marker=dict(size=8, color="#1565C0", symbol="square"),
                showlegend=False, hovertemplate="DI_int: %{y:+.2f}<extra></extra>"))

        fig_tl.add_hrect(y0=-3.5, y1=-0.3, fillcolor="#FFCDD2", opacity=0.25, line_width=0)
        fig_tl.add_hrect(y0=-0.3, y1=0.3, fillcolor="#C8E6C9", opacity=0.3, line_width=0)
        fig_tl.add_hrect(y0=0.3, y1=3.5, fillcolor="#BBDEFB", opacity=0.25, line_width=0)
        fig_tl.add_hline(y=0, line_dash="solid", line_color="#999999", line_width=1, opacity=0.5)

        ERDP_SHORT = {"A. 총체적과장형": "A", "B. 외부미화형": "B", "C. 내부은폐형": "C",
                      "D. 균형일치형": "D", "E. 총체적과소형": "E", "F. ESG미성숙": "F"}
        for _, row in timeline.iterrows():
            t = row["ERDP_유형"]
            tinfo = TYPE_INFO.get(t, TYPE_INFO["N/A"])
            di_val = row["DI_ext"]
            fig_tl.add_trace(go.Scatter(
                x=[row["분기"]], y=[4.5], mode="markers+text",
                marker=dict(size=42, color=tinfo["color"], line=dict(width=2, color="white"), symbol="circle"),
                text=[ERDP_SHORT.get(t, "?")], textposition="middle center",
                textfont=dict(size=14, color="white", family="Arial Black"),
                hovertext=(f"<b>{row['분기']}</b><br>ERDP: {t}<br>"
                    f"DI_ext: {di_val:+.1f} (미디어 vs 공시)<br>"
                    f"DI_int: {row['DI_int']:+.1f} (직원 vs 공시)")
                    if pd.notna(di_val) else f"<b>{row['분기']}</b><br>데이터 없음",
                hoverinfo="text", showlegend=False))

        fig_tl.update_layout(
            height=550, margin=dict(t=10, b=100, l=50, r=20),
            yaxis=dict(range=[-3.5, 5.5], title="DI 값", zeroline=False, tickfont=dict(size=10)),
            xaxis=dict(tickangle=-45, tickfont=dict(size=11), dtick=1),
            legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center", font=dict(size=14)),
            annotations=[
                dict(text="<b>그린워싱 영역</b>", x=0.01, y=-2.5, xref="paper",
                     showarrow=False, font=dict(size=13, color="#C62828")),
                dict(text="<b>균형 영역</b>", x=0.01, y=0, xref="paper",
                     showarrow=False, font=dict(size=13, color="#2E7D32")),
                dict(text="<b>보수적 공시 영역</b>", x=0.01, y=2.5, xref="paper",
                     showarrow=False, font=dict(size=13, color="#1565C0")),
            ])
        st.plotly_chart(fig_tl, use_container_width=True)

        type_counts = timeline["ERDP_유형"].value_counts()
        total_q = len(timeline)
        danger_q = sum(type_counts.get(t, 0) for t in ["A. 총체적과장형", "B. 외부미화형"])
        ok_q = type_counts.get("D. 균형일치형", 0)
        st.markdown(
            f"<p style='text-align:center; font-size:16px;'>"
            f"<b>요약</b>: 전체 {total_q}개 분기 중 "
            f"<span style='color:#C62828; font-weight:bold;'>위험 {danger_q}분기</span> / "
            f"<span style='color:#2E7D32; font-weight:bold;'>양호 {ok_q}분기</span> / "
            f"기타 {total_q - danger_q - ok_q}분기</p>", unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════
# 3행: 직원 인식 상세 + 산업 내 위치
# ═══════════════════════════════════════════════════
col_c, col_d = st.columns([1, 1])

with col_c:
    st.markdown("### 직원이 느끼는 우리 회사")
    if latest_valid is not None:
        items = {"급여/복지": latest_valid.get("JP_급여복지", np.nan),
                 "워라밸": latest_valid.get("JP_워라밸", np.nan),
                 "사내문화": latest_valid.get("JP_사내문화", np.nan),
                 "비전": latest_valid.get("JP_비전", np.nan),
                 "경영진": latest_valid.get("JP_경영진", np.nan)}
        for label, val in items.items():
            if pd.notna(val):
                st.markdown(f"**{label}**")
                st.progress(val / 5.0, text=f"{val:.1f} / 5.0")
            else:
                st.markdown(f"**{label}** - 데이터 없음")

with col_d:
    st.markdown("### 산업군 내 위치")
    ind_data = df[df["산업군"] == industry].copy()
    ind_mean = ind_data.groupby("기업명")["DI_ext"].mean().dropna().sort_values()
    if len(ind_mean) > 0:
        colors = ["#000000" if c_name == sel_corp else
                  "#EF5350" if ind_mean[c_name] < -0.3 else
                  "#42A5F5" if ind_mean[c_name] > 0.3 else "#66BB6A"
                  for c_name in ind_mean.index]
        widths = [3 if c_name == sel_corp else 0 for c_name in ind_mean.index]
        fig_rank = go.Figure()
        fig_rank.add_trace(go.Bar(
            y=ind_mean.index, x=ind_mean.values, orientation="h",
            marker=dict(color=colors, line=dict(width=widths, color="black")),
            text=[f"{v:+.2f}" for v in ind_mean.values],
            textposition="outside", textfont=dict(size=10)))
        fig_rank.add_vline(x=0, line_dash="solid", line_color="gray", opacity=0.5)
        fig_rank.add_vline(x=-0.3, line_dash="dot", line_color="red", opacity=0.3)
        fig_rank.add_vline(x=0.3, line_dash="dot", line_color="blue", opacity=0.3)
        fig_rank.add_annotation(x=-1.5, y=-0.8, text="<- 과장공시 (그린워싱)",
                               showarrow=False, font=dict(size=9, color="#EF5350"))
        fig_rank.add_annotation(x=1.5, y=-0.8, text="보수적 공시 ->",
                               showarrow=False, font=dict(size=9, color="#42A5F5"))
        fig_rank.update_layout(
            height=max(250, len(ind_mean) * 35),
            margin=dict(t=10, b=40, l=10, r=60),
            xaxis_title="DI_ext 평균", yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_rank, use_container_width=True)

st.divider()

# ═══════════════════════════════════════════════════
# 4행: 시계열 추이
# ═══════════════════════════════════════════════════
with st.expander("상세 추이 보기", expanded=False):
    tab1, tab2, tab3 = st.tabs(["미디어 감성 추이", "직원 만족도 추이", "주가 변동성 추이"])

    with tab1:
        valid_bk = cd.dropna(subset=["BK_감성"])
        if len(valid_bk) > 0:
            fig_bk = go.Figure()
            fig_bk.add_trace(go.Bar(
                x=valid_bk["분기"], y=valid_bk["BK_감성"],
                marker_color=["#66BB6A" if v > 0.1 else "#EF5350" if v < -0.1 else "#FFA726"
                              for v in valid_bk["BK_감성"]],
                text=[f"{v:+.2f}" for v in valid_bk["BK_감성"]],
                textposition="outside", textfont=dict(size=9)))
            fig_bk.add_hline(y=0, line_color="gray", line_dash="dash")
            fig_bk.update_layout(height=300, margin=dict(t=10, b=30),
                yaxis_title="FinBERT 감성 점수", yaxis=dict(range=[-1.2, 1.2]))
            st.plotly_chart(fig_bk, use_container_width=True)

    with tab2:
        jp_valid = cd.dropna(subset=["JP_종합"])
        if len(jp_valid) > 0:
            fig_jp = go.Figure()
            fig_jp.add_trace(go.Scatter(x=jp_valid["분기"], y=jp_valid["JP_S"],
                mode="lines+markers", name="S차원 (급여/워라밸/사내문화)",
                line=dict(color="#FF7043", width=2)))
            fig_jp.add_trace(go.Scatter(x=jp_valid["분기"], y=jp_valid["JP_G"],
                mode="lines+markers", name="G차원 (비전/경영진)",
                line=dict(color="#5C6BC0", width=2)))
            fig_jp.add_trace(go.Scatter(x=jp_valid["분기"], y=jp_valid["JP_종합"],
                mode="lines+markers", name="종합", line=dict(color="#333333", width=3)))
            fig_jp.update_layout(height=300, margin=dict(t=10, b=30),
                yaxis_title="평점 (5점 만점)", yaxis=dict(range=[1, 5]),
                legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_jp, use_container_width=True)

    with tab3:
        if "변동성_연율화" in cd.columns:
            vol_valid = cd.dropna(subset=["변동성_연율화"])
            if len(vol_valid) > 0:
                fig_vol = go.Figure()
                fig_vol.add_trace(go.Bar(
                    x=vol_valid["분기"], y=vol_valid["변동성_연율화"] * 100,
                    marker_color=["#EF5350" if v > 0.5 else "#FFA726" if v > 0.35 else "#66BB6A"
                                  for v in vol_valid["변동성_연율화"]],
                    text=[f"{v*100:.1f}%" for v in vol_valid["변동성_연율화"]],
                    textposition="outside", textfont=dict(size=9)))
                ind_avg = df[df["산업군"] == industry]["변동성_연율화"].mean()
                fig_vol.add_hline(y=ind_avg*100, line_dash="dash", line_color="blue",
                                 opacity=0.5, annotation_text=f"산업 평균 {ind_avg*100:.1f}%")
                fig_vol.update_layout(height=300, margin=dict(t=10, b=30),
                    yaxis_title="연율화 변동성 (%)")
                st.plotly_chart(fig_vol, use_container_width=True)

# ── 하단 ──
st.divider()
st.caption("ESG 그린워싱 모니터링 대시보드 v3.0 | KCGS + 빅카인즈(FinBERT) + 잡플래닛 + Yahoo Finance | 2023~2025")
