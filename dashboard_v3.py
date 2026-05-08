# -*- coding: utf-8 -*-
"""
dashboard_v3.py — ESG 그린워싱 모니터링 대시보드 (Streamlit Cloud 배포본)
실행: streamlit run dashboard_v3.py

※ 파일명은 dashboard_v3.py (Streamlit Cloud 기존 진입점 호환용)이지만,
  내용은 v5 기준으로 전면 갱신되어 있음. 로컬 개발본:
  VS_CODE 분석/10_대시보드_코드/dashboard_v5.py

주요 내용 (재검증 결과, 2026-04-25 기준):
  - 720 관측치 (60 기업 × 12 분기, 잡플래닛 646건 보완 반영)
  - H2 β=+0.216*** (cluster-robust SE by 기업)
  - H3 S≈G null finding (Wald p=0.968)
  - H4 Joint F(5)=3.33** → 4.94*** (통제 포함 시 강화)
  - H5 시차 분석: DI_int→JP 동시효과만 유의, DI_ext→변동성 전 시차 비유의
  - 분기 슬라이더, ERDP 6-type 2차원 매트릭스(분기 궤적) 제공
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

# ── 데이터 로드 (0422 CSV 우선, 여러 소스 fallback) ──
def _data_mtime():
    candidates = [
        Path("./output/di_all60_finbert.xlsx"),
        Path("./output/di_all60_finbert_final.xlsx"),
        Path("./output/di_all60_finbert_final.csv"),
        Path("./output/stock_volatility_quarterly.csv"),
    ]
    return tuple(p.stat().st_mtime if p.exists() else 0 for p in candidates)

@st.cache_data
def load_data(_mtime=None):
    import warnings
    warnings.filterwarnings("ignore")

    # 경로 기준점 두 개:
    #   _BASE      = 로컬: VS_CODE 분석/ (스크립트가 10_대시보드_코드/에 있을 때)
    #   _REPO_ROOT = GitHub 배포: 레포 루트 (스크립트가 루트에 있을 때) → ./output/
    _SCRIPT    = Path(__file__).resolve()
    _BASE      = _SCRIPT.parent.parent
    _REPO_ROOT = _SCRIPT.parent

    # 1순위: 논문·분석 스크립트가 사용하는 최종 CSV (가설 검증 결과와 동일 소스)
    csv0422_candidates = [
        _BASE / "06_집계_결과_데이터" / "di_all60_finbert_final.csv",
        _REPO_ROOT / "output" / "di_all60_finbert_final.csv",
        _BASE / "06_집계_결과_데이터" / "di_all60_finbert_updated_0422.xlsx - CSV_Export.csv",
        Path("./06_집계_결과_데이터/di_all60_finbert_final.csv"),
        Path("./output/di_all60_finbert_final.csv"),
        Path("./06_집계_결과_데이터/di_all60_finbert_updated_0422.xlsx - CSV_Export.csv"),
        Path("./di_all60_finbert_final.csv"),
        Path("./di_all60_finbert_updated_0422.xlsx - CSV_Export.csv"),
    ]
    csv0422_path = next((p for p in csv0422_candidates if p.exists()), None)

    if csv0422_path is not None:
        df = pd.read_csv(csv0422_path)
        # 첫 데이터 행(index 0)은 수식·설명 행이므로 제거
        df = df.iloc[1:].reset_index(drop=True)
        # 숫자형 변환
        num_cols = [
            "KCGS_종합","KCGS_E","KCGS_S","KCGS_G",
            "KCGS_종합_mean","KCGS_종합_std","KCGS_E_mean","KCGS_E_std",
            "KCGS_S_mean","KCGS_S_std","KCGS_G_mean","KCGS_G_std",
            "Z_KCGS_종합","Z_KCGS_E","Z_KCGS_S","Z_KCGS_G",
            "BK_감성","BK_긍정수","BK_부정수","BK_중립수","BK_총건수",
            "JP_종합","JP_급여복지","JP_워라밸","JP_사내문화","JP_비전","JP_경영진","JP_n",
            "JP_S","JP_G","Z_BK","Z_JP","Z_JP_S","Z_JP_G",
            "DI_ext","DI_int","DI_gap","DI_int_S","DI_int_G",
        ]
        for c in num_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        if "연도" in df.columns:
            df["연도"] = pd.to_numeric(df["연도"], errors="coerce").astype("Int64")
        if "ERDP_유형" in df.columns:
            df["ERDP_유형"] = df["ERDP_유형"].fillna("N/A").astype(str)
        else:
            df["ERDP_유형"] = "N/A"
    else:
        # 2순위: reanalysis_data.csv (예비 경로)
        csv_candidates = [
            _BASE / "06_집계_결과_데이터" / "reanalysis_data.csv",
            _REPO_ROOT / "output" / "reanalysis_data.csv",
            _BASE / "reanalysis_data.csv",
            Path("./06_집계_결과_데이터/reanalysis_data.csv"),
            Path("./output/reanalysis_data.csv"),
            Path("./reanalysis_data.csv"),
        ]
        csv_path = next((p for p in csv_candidates if p.exists()), None)

        if csv_path is not None:
            df = pd.read_csv(csv_path)
            rename_map = {
                "BK_pos":"BK_긍정수", "BK_neg":"BK_부정수",
                "BK_neu":"BK_중립수", "BK_total":"BK_총건수",
                "ERDP":"ERDP_유형",
            }
            df = df.rename(columns=rename_map)
            df["ERDP_유형"] = df["ERDP_유형"].fillna("N/A").astype(str)
        else:
            # 3순위: 엑셀 fallback
            xlsx_candidates = [
                _BASE / "06_집계_결과_데이터" / "di_all60_finbert_final.xlsx",
                _REPO_ROOT / "output" / "di_all60_finbert_final.xlsx",
                _BASE / "06_집계_결과_데이터" / "di_all60_finbert_updated.xlsx",
                _REPO_ROOT / "output" / "di_all60_finbert.xlsx",
                Path("./06_집계_결과_데이터/di_all60_finbert_final.xlsx"),
                Path("./output/di_all60_finbert_final.xlsx"),
                Path("./06_집계_결과_데이터/di_all60_finbert_updated.xlsx"),
                Path("./output/di_all60_finbert_updated.xlsx"),
                Path("./output/di_all60_finbert.xlsx"),
                Path("./di_all60_finbert_updated.xlsx"),
            ]
            xlsx_path = next((p for p in xlsx_candidates if p.exists()), None)
            if xlsx_path is None:
                st.error(
                    "데이터 파일을 찾을 수 없습니다.\n"
                    "- 1순위: 06_집계_결과_데이터/di_all60_finbert_updated_0422.xlsx - CSV_Export.csv\n"
                    "- 2순위: 06_집계_결과_데이터/reanalysis_data.csv\n"
                    "- 3순위: 06_집계_결과_데이터/di_all60_finbert_updated.xlsx"
                )
                st.stop()

            # 시트/헤더 자동 감지
            #  - 구버전(_0422.xlsx 형식): "DI_전체데이터" 시트, header=1
            #  - "CSV_Export" 시트(설명 행 포함): header=0, skiprows=[1]
            #  - 그 외(예: 계산값 baked in xlsx): 첫 시트, header=0
            _xls = pd.ExcelFile(xlsx_path)
            if "DI_전체데이터" in _xls.sheet_names:
                df = pd.read_excel(xlsx_path, sheet_name="DI_전체데이터", header=1)
            elif "CSV_Export" in _xls.sheet_names:
                df = pd.read_excel(xlsx_path, sheet_name="CSV_Export", header=0, skiprows=[1])
            else:
                df = pd.read_excel(xlsx_path, sheet_name=_xls.sheet_names[0], header=0)
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
            df = df.iloc[:, :len(cols)]
            df.columns = cols
            for c in cols:
                if c not in {"기업명","산업군","분기","ERDP_유형"}:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            # 엑셀이 수식 셀이라 Z/DI/ERDP 컬럼이 비어 있을 때만 재계산
            # (값이 이미 채워진 xlsx는 분석 스크립트 결과를 그대로 신뢰 → 로컬·배포 일관성)
            _needs_recompute = df["DI_ext"].isna().all() or df["Z_BK"].isna().all()
            if _needs_recompute:
                for kc in ["KCGS_종합","KCGS_E","KCGS_S","KCGS_G"]:
                    grp = df.groupby(["산업군","연도"])[kc]
                    df[f"Z_{kc}"] = (df[kc] - grp.transform("mean")) / grp.transform("std")
                def within_firm_z(s):
                    sd = s.std(ddof=0)
                    return (s - s.mean()) / sd if sd and sd > 0 else s * 0
                df["Z_BK"]   = df.groupby("기업명")["BK_감성"].transform(within_firm_z)
                df["Z_JP"]   = df.groupby("기업명")["JP_종합"].transform(within_firm_z)
                df["Z_JP_S"] = df.groupby("기업명")["JP_S"].transform(within_firm_z)
                df["Z_JP_G"] = df.groupby("기업명")["JP_G"].transform(within_firm_z)
                df["DI_ext"]   = df["Z_BK"]   - df["Z_KCGS_종합"]
                df["DI_int"]   = df["Z_JP"]   - df["Z_KCGS_종합"]
                df["DI_gap"]   = df["DI_ext"] - df["DI_int"]
                df["DI_int_S"] = df["Z_JP_S"] - df["Z_KCGS_S"]
                df["DI_int_G"] = df["Z_JP_G"] - df["Z_KCGS_G"]

                def _classify(row):
                    ext, intv, kcgs = row["DI_ext"], row["DI_int"], row["KCGS_종합"]
                    if pd.isna(ext) or pd.isna(intv): return "N/A"
                    if pd.notna(kcgs) and kcgs <= 0: return "F. ESG미성숙"
                    theta = 0.3
                    if ext < -theta and intv < -theta: return "A. 총체적과장형"
                    if ext < -theta and intv >  theta: return "B. 외부미화형"
                    if ext >  theta and intv < -theta: return "C. 내부은폐형"
                    if ext >  theta and intv >  theta: return "E. 총체적과소형"
                    return "D. 균형일치형"
                df["ERDP_유형"] = df.apply(_classify, axis=1)
            else:
                # 값이 이미 있는 경우 ERDP_유형의 NaN만 'N/A' 문자열로 정규화
                df["ERDP_유형"] = df["ERDP_유형"].fillna("N/A").astype(str)

    # 주가 변동성 CSV 병합 (있을 때만)
    vol_candidates = [
        _BASE / "06_집계_결과_데이터" / "stock_volatility_quarterly.csv",
        _REPO_ROOT / "output" / "stock_volatility_quarterly.csv",
        _BASE / "stock_volatility_quarterly.csv",
        Path("./06_집계_결과_데이터/stock_volatility_quarterly.csv"),
        Path("./output/stock_volatility_quarterly.csv"),
        Path("./stock_volatility_quarterly.csv"),
    ]
    vol_path = next((p for p in vol_candidates if p.exists()), None)
    if vol_path is not None:
        df_vol = pd.read_csv(vol_path)
        df = df.merge(df_vol[["기업명","분기","변동성_연율화","누적수익률"]],
                      on=["기업명","분기"], how="left")
    return df

df = load_data(_data_mtime())

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

    # 분기 선택 슬라이더 (논문 케이스 재현용, v4 추가)
    _corp_df = df[df["기업명"] == sel_corp].sort_values("분기")
    all_quarters = _corp_df["분기"].unique().tolist()
    _valid_quarters = _corp_df[~_corp_df["ERDP_유형"].isin(["N/A"])]["분기"].tolist()
    default_q = _valid_quarters[-1] if _valid_quarters else all_quarters[-1]
    sel_quarter = st.select_slider(
        "분기 선택",
        options=all_quarters,
        value=default_q,
        help="12분기 중 원하는 시점 선택 (예: SK텔레콤 2025Q2 USIM 유출 사태)"
    )

    st.divider()
    st.markdown("**ERDP 유형 범례**")
    for t, info in TYPE_INFO.items():
        if t != "N/A":
            st.markdown(f"**{info['icon']} {info['label']}** - {info['desc'][:20]}...")

    st.divider()
    st.caption(
        "**데이터**: 720 관측치 (JP 646건 보완, 2026-04-25 재검증)\n\n"
        "**논문 v23 핵심**: H1 ANOVA F=250.0(p<.001) · H2 β=+0.216\\*\\*\\* · "
        "H3 null finding(S≈G, Wald p=0.97) · H4 Joint F(5)=3.33\\*\\* → 4.94\\*\\*\\*(통제 포함) · "
        "H5 시차 비유의 (이해관계자 비대칭성 확인)"
    )

# ── 기업 데이터 ──
cd = df[df["기업명"] == sel_corp].sort_values("분기").reset_index(drop=True)
industry = cd["산업군"].iloc[0]
ind_kr = IND_KR.get(industry, industry)

# 선택된 분기의 행 (v4: latest_valid → sel_quarter 기반)
sel_row_df = cd[cd["분기"] == sel_quarter]
latest_valid = sel_row_df.iloc[0] if len(sel_row_df) > 0 and sel_row_df.iloc[0]["ERDP_유형"] != "N/A" else None
# fallback: 유효 데이터 없으면 최신 유효 분기로
if latest_valid is None:
    _v = cd[~cd["ERDP_유형"].isin(["N/A"])]
    latest_valid = _v.iloc[-1] if len(_v) > 0 else None

# ═══════════════════════════════════════════════════
# 헤더
# ═══════════════════════════════════════════════════
if latest_valid is not None:
    etype = latest_valid["ERDP_유형"]
    info = TYPE_INFO.get(etype, TYPE_INFO["N/A"])

    st.markdown(f"# {info['icon']} {sel_corp}")
    q_label = latest_valid['분기']
    _q_tag = "선택 분기" if q_label == sel_quarter else "최신 유효 분기"
    st.markdown(f"### {ind_kr} ({industry}) | {_q_tag}: **:blue[{q_label}]**")

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
# 신규 (v4): ERDP 6-type 2차원 매트릭스 — 분기별 궤적
# 논문 v22 그림 1-2 와 동일한 DI_ext × DI_int 2차원 평면에
# 선택 기업의 12분기 경로를 표시, 선택 분기는 별표로 강조
# ═══════════════════════════════════════════════════
st.markdown("### ERDP 6-type 2차원 매트릭스 — 분기별 궤적")
st.caption("선택한 기업이 **12분기 동안 어느 유형 영역을 이동했는지** 시각화. 선택 분기는 별표(★)로 강조.")

col_m1, col_m2 = st.columns([3, 1])
with col_m1:
    matrix_df = cd.dropna(subset=["DI_ext","DI_int"]).copy()
    if len(matrix_df) > 0:
        fig_mat = go.Figure()
        theta = 0.3
        # 유형별 의미·색상 매핑 (사이드바 TYPE_INFO와 동일 톤)
        # A=빨강(위험), B=오렌지빨강, C=주황, D=초록(양호), E=파랑
        zones = [
            (-3.5, -theta, -3.5, -theta, "#FFCDD2", "A"),   # 빨강 (#EF5350 연한 톤)
            (-3.5, -theta,  theta,  3.5, "#FFCCBC", "B"),   # 오렌지빨강 (#FF8A65)
            ( theta,  3.5, -3.5, -theta, "#FFE0B2", "C"),   # 주황 (#FFA726)
            (-theta,  theta, -theta,  theta, "#C8E6C9", "D"),   # 초록 (#66BB6A)
            ( theta,  3.5,  theta,  3.5, "#BBDEFB", "E"),   # 파랑 (#42A5F5)
        ]
        for x1, x2, y1, y2, color, _l in zones:
            fig_mat.add_shape(type="rect", x0=x1, x1=x2, y0=y1, y1=y2,
                              fillcolor=color, opacity=0.55, line=dict(width=0), layer="below")
        # 유형 라벨 (색상도 강조 톤으로)
        letter_colors = {"A":"#C62828","B":"#D84315","C":"#E65100",
                         "D":"#2E7D32","E":"#1565C0"}
        for x, y, letter in [(-1.8,-1.8,"A"), (-1.8,1.8,"B"), (1.8,-1.8,"C"),
                              (0,0,"D"), (1.8,1.8,"E")]:
            fig_mat.add_annotation(
                x=x, y=y, text=f"<b>{letter}</b>", showarrow=False,
                font=dict(size=32, color=letter_colors[letter]), opacity=0.55)

        # 임계값 선
        for v in [-theta, theta]:
            fig_mat.add_hline(y=v, line_dash="dash", line_color="red", opacity=0.35)
            fig_mat.add_vline(x=v, line_dash="dash", line_color="red", opacity=0.35)
        fig_mat.add_hline(y=0, line_color="gray", line_width=0.5, opacity=0.3)
        fig_mat.add_vline(x=0, line_color="gray", line_width=0.5, opacity=0.3)

        # 분기별 궤적 (선 + 작은 원 마커)
        fig_mat.add_trace(go.Scatter(
            x=matrix_df["DI_ext"], y=matrix_df["DI_int"],
            mode="lines+markers",
            line=dict(color="#37474F", width=1.5, dash="dot"),
            marker=dict(size=9, color="#37474F", line=dict(width=1, color="white")),
            text=[f"{q}<br>ERDP: {t}" for q, t in
                  zip(matrix_df["분기"], matrix_df["ERDP_유형"])],
            hovertemplate="<b>%{text}</b><br>DI_ext: %{x:+.2f}<br>DI_int: %{y:+.2f}<extra></extra>",
            name="분기 궤적"))

        # 각 분기 라벨 (선택 분기 제외)
        for _, r in matrix_df.iterrows():
            if r["분기"] != sel_quarter:
                fig_mat.add_annotation(
                    x=r["DI_ext"], y=r["DI_int"], text=r["분기"][-4:],
                    showarrow=False, yshift=14, font=dict(size=9, color="#37474F"))

        # 선택 분기 강조 — 정확한 포인트 + 십자선 + 값 라벨
        sel_row_m = matrix_df[matrix_df["분기"] == sel_quarter]
        if len(sel_row_m) > 0:
            sx = float(sel_row_m["DI_ext"].iloc[0])
            sy = float(sel_row_m["DI_int"].iloc[0])

            # 축까지 십자선 (dashed)
            fig_mat.add_shape(type="line", x0=sx, x1=sx, y0=-3.5, y1=sy,
                              line=dict(color="#FFC107", width=1.5, dash="dash"), layer="above")
            fig_mat.add_shape(type="line", x0=-3.5, x1=sx, y0=sy, y1=sy,
                              line=dict(color="#FFC107", width=1.5, dash="dash"), layer="above")

            # 정확 포인트 (큰 원 + 내부 점)
            fig_mat.add_trace(go.Scatter(
                x=[sx], y=[sy], mode="markers",
                marker=dict(size=22, color="rgba(255,193,7,0.35)",
                            line=dict(width=2, color="#FFC107")),
                hovertemplate=f"<b>선택 분기: {sel_quarter}</b><br>DI_ext: {sx:+.3f}<br>DI_int: {sy:+.3f}<extra></extra>",
                showlegend=False))
            fig_mat.add_trace(go.Scatter(
                x=[sx], y=[sy], mode="markers",
                marker=dict(size=8, color="#F57C00",
                            line=dict(width=1.5, color="white"), symbol="circle"),
                hoverinfo="skip", showlegend=False))

            # 선택 분기 라벨 (박스 형태)
            fig_mat.add_annotation(
                x=sx, y=sy,
                text=f"<b>{sel_quarter}</b><br>({sx:+.2f}, {sy:+.2f})",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=1.5,
                arrowcolor="#F57C00",
                ax=40, ay=-40,
                bgcolor="#FFF8E1", bordercolor="#F57C00", borderwidth=1.5,
                font=dict(size=11, color="#E65100", family="Arial Black"),
                opacity=0.95)

            # 축 눈금에 선택 값 표시 (빨간 화살표)
            fig_mat.add_annotation(
                x=sx, y=-3.5, text=f"<b>{sx:+.2f}</b>",
                showarrow=False, yshift=-8,
                font=dict(size=10, color="#F57C00"))
            fig_mat.add_annotation(
                x=-3.5, y=sy, text=f"<b>{sy:+.2f}</b>",
                showarrow=False, xshift=-25,
                font=dict(size=10, color="#F57C00"))

        fig_mat.update_layout(
            height=470, margin=dict(t=30, b=40, l=50, r=30),
            xaxis=dict(title="DI_ext (시장 괴리 = Z_BK − Z_KCGS)",
                       range=[-3.5, 3.5], zeroline=False),
            yaxis=dict(title="DI_int (조직 괴리 = Z_JP − Z_KCGS)",
                       range=[-3.5, 3.5], zeroline=False),
            showlegend=False,
            title=dict(text=f"{sel_corp}의 12분기 ERDP 경로",
                       x=0.5, font=dict(size=14)))
        st.plotly_chart(fig_mat, use_container_width=True)
    else:
        st.info("DI 데이터가 부족하여 매트릭스를 표시할 수 없습니다.")

with col_m2:
    st.markdown("#### 유형 해석 (영역 색상)")
    st.markdown(
        '<div style="font-size:13px; line-height:1.8;">'
        '<div style="background:#FFCDD2; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#C62828;">A 빨강</b> (좌하): 공시 과장 + 직원 불만족 → <b>그린워싱 위험 최고</b>'
        '</div>'
        '<div style="background:#FFCCBC; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#D84315;">B 주황빨강</b> (좌상): 미디어만 부정 + 직원 긍정'
        '</div>'
        '<div style="background:#FFE0B2; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#E65100;">C 주황</b> (우하): 미디어 긍정 + 직원 부정'
        '</div>'
        '<div style="background:#C8E6C9; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#2E7D32;">D 초록</b> (중앙): 공시=실제 → <b>양호</b>'
        '</div>'
        '<div style="background:#BBDEFB; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#1565C0;">E 파랑</b> (우상): 공시 < 실제 → 보수적'
        '</div>'
        '<div style="background:#E0E0E0; padding:6px 10px; border-radius:4px; margin:3px 0;">'
        '<b style="color:#616161;">F 회색</b> (별도): KCGS D등급'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.caption("★ 노란 포인트 = 선택 분기 (정확 좌표 + 축 투영)\n\n"
               "**축**: 좌=미디어 부정, 우=미디어 긍정, 하=직원 부정, 상=직원 긍정")

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
st.caption("ESG 그린워싱 모니터링 대시보드 (재검증 수치 반영) | KCGS + 빅카인즈(FinBERT) + 잡플래닛(720건) + Yahoo Finance | 2023~2025 | 가설 검증 기준일 2026-04-25")
