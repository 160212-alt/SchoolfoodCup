
import random
import uuid

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client


# =====================================
# 기본 설정
# =====================================
st.set_page_config(
    page_title="급식 반찬 월드컵",
    page_icon="🏆",
    layout="wide",
)

MENUS = [
    "제육볶음",
    "간장찜닭",
    "가자미순살튀김",
    "돈육불백",
    "미트볼데리야끼볶음",
    "수육",
    "진미채고추장볶음",
    "치즈떡닭갈비",
]

ROUND_NAMES = ["8강", "4강", "결승"]
PAGE_SIZE = 1000

st.title("🏆 급식 반찬 월드컵")
st.caption("내가 좋아하는 반찬을 고르고, 우리 학급의 선택 결과도 확인해 보세요.")


# =====================================
# Supabase 연결
# =====================================
@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


# =====================================
# 전체 대결 기록 조회
# =====================================
def load_all_duels():
    """기존 menu_duels 표에서 필요한 여섯 열을 모두 읽는다."""
    client = get_supabase()
    all_rows = []
    offset = 0

    while True:
        response = (
            client.table("menu_duels")
            .select(
                "id, game_id, round, left_menu, right_menu, winner"
            )
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )

        rows = response.data

        if not isinstance(rows, list):
            raise RuntimeError("조회 결과 형식이 올바르지 않습니다.")

        all_rows.extend(rows)

        if len(rows) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return all_rows


# =====================================
# 학급 전체 통계 계산
# =====================================
def analyze_duels(rows):
    stats = {
        menu: {
            "반찬": menu,
            "대결 수": 0,
            "승리 수": 0,
            "승률": None,
            "우승 횟수": 0,
        }
        for menu in MENUS
    }

    for row in rows:
        left = row.get("left_menu")
        right = row.get("right_menu")
        winner = row.get("winner")
        round_name = row.get("round")

        # 양쪽 반찬 모두 대결 수에 포함
        if left in stats:
            stats[left]["대결 수"] += 1

        if right in stats:
            stats[right]["대결 수"] += 1

        # 승리 수
        if winner in stats:
            stats[winner]["승리 수"] += 1

        # 결승전 승자는 우승 1회
        if round_name == "결승" and winner in stats:
            stats[winner]["우승 횟수"] += 1

    for menu in MENUS:
        matches = stats[menu]["대결 수"]
        wins = stats[menu]["승리 수"]

        if matches > 0:
            stats[menu]["승률"] = wins / matches * 100

    df = pd.DataFrame(list(stats.values()))

    # 승률 높은 순서, 동률이면 승리 수와 대결 수 순
    # 대결 기록이 없는 반찬은 표의 아래쪽으로 배치
    df["_기록없음"] = df["승률"].isna()

    df = df.sort_values(
        by=["_기록없음", "승률", "승리 수", "대결 수", "반찬"],
        ascending=[True, False, False, False, True],
        kind="stable",
    ).drop(columns=["_기록없음"])

    return df


# =====================================
# 새 게임 시작
# =====================================
def start_game():
    menus = MENUS.copy()
    random.shuffle(menus)

    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.participants = menus
    st.session_state.round_index = 0
    st.session_state.match_index = 0
    st.session_state.round_winners = []
    st.session_state.champion = None
    st.session_state.locked = False


if "game_id" not in st.session_state:
    start_game()


# =====================================
# 대결 결과 저장 및 확인
# =====================================
def save_duel(round_name, left_menu, right_menu, winner):
    if left_menu == right_menu:
        raise ValueError("서로 다른 반찬을 선택해야 합니다.")

    payload = {
        "game_id": st.session_state.game_id,
        "round": round_name,
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    response = (
        get_supabase()
        .table("menu_duels")
        .insert(payload)
        .select("id, game_id, round, left_menu, right_menu, winner")
        .execute()
    )

    rows = response.data

    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("저장 결과를 확인할 수 없습니다.")

    saved = rows[0]

    for column, expected in payload.items():
        if saved.get(column) != expected:
            raise RuntimeError("저장 결과가 요청 내용과 다릅니다.")

    if saved.get("id") is None:
        raise RuntimeError("저장된 행의 ID를 확인할 수 없습니다.")

    return saved


# =====================================
# 월드컵 화면
# =====================================
def show_game():
    st.subheader("🎮 월드컵 진행")

    # 저장 여부를 확인할 수 없는 상태
    if st.session_state.locked:
        st.error("⚠️ 대결 결과의 저장 여부를 확인할 수 없습니다.")
        st.warning(
            "재선택과 다음 대결 진행을 잠갔습니다. "
            "교사가 menu_duels 표에서 저장 여부를 확인해야 합니다. "
            "중복 저장을 막기 위해 이 상태에서 다시 선택하지 마세요."
        )
        return

    # 우승 결과
    if st.session_state.champion is not None:
        st.balloons()
        st.success("🏆 최종 우승 반찬")
        st.header(f"🥇 {st.session_state.champion}")
        st.write("월드컵이 끝났습니다!")
        
        if st.button("🔄 다시 시작하기", use_container_width=True):
            start_game()
            st.rerun()

        st.info(
            "학급 전체 기록은 '📊 전체 기록 분석' 탭에서 확인할 수 있습니다."
        )
        return

    round_index = st.session_state.round_index
    match_index = st.session_state.match_index
    round_name = ROUND_NAMES[round_index]
    menus = st.session_state.participants

    left_menu = menus[match_index * 2]
    right_menu = menus[match_index * 2 + 1]

    completed = sum(
        len(st.session_state.participants) // 2
        for _ in []
    )

    # 라운드별로 완료한 대결 수 계산
    completed = (
        0 if round_index == 0
        else 4 if round_index == 1
        else 6
    ) + match_index

    st.progress(completed / 7)
    st.write(f"**{round_name}** · {match_index + 1}번째 대결")
    st.write(f"총 7번 중 {completed + 1}번째 선택")
    st.write("더 먹고 싶은 반찬 하나를 선택하세요.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            f"""
            <div style="
                border:2px solid #ff8a65;
                border-radius:16px;
                padding:24px 8px;
                text-align:center;
                min-height:120px;
                display:flex;
                flex-direction:column;
                justify-content:center;
            ">
                <div style="font-size:36px;">🍚</div>
                <div style="font-size:22px;font-weight:bold;">
                    {left_menu}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        choose_left = st.button(
            left_menu,
            key=f"left_{st.session_state.game_id}_{completed}",
            use_container_width=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style="
                border:2px solid #64b5f6;
                border-radius:16px;
                padding:24px 8px;
                text-align:center;
                min-height:120px;
                display:flex;
                flex-direction:column;
                justify-content:center;
            ">
                <div style="font-size:36px;">🍚</div>
                <div style="font-size:22px;font-weight:bold;">
                    {right_menu}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        choose_right = st.button(
            right_menu,
            key=f"right_{st.session_state.game_id}_{completed}",
            use_container_width=True,
        )

    if choose_left or choose_right:
        winner = left_menu if choose_left else right_menu

        try:
            save_duel(round_name, left_menu, right_menu, winner)
        except Exception:
            st.session_state.locked = True
            st.rerun()

        # 저장 확인 성공 후에만 다음 단계로 이동
        st.session_state.round_winners.append(winner)
        st.session_state.match_index += 1

        matches_in_round = len(menus) // 2

        if st.session_state.match_index >= matches_in_round:
            winners = st.session_state.round_winners.copy()

            if round_index == 2:
                st.session_state.champion = winners[0]
            else:
                st.session_state.participants = winners
                st.session_state.round_winners = []
                st.session_state.round_index += 1
                st.session_state.match_index = 0

        st.rerun()


# =====================================
# 전체 기록 분석 화면
# =====================================
def show_analysis():
    st.subheader("📊 학급 전체 대결 기록 분석")
    st.write(
        "현재까지 menu_duels에 저장된 모든 대결을 분석합니다. "
        "진행 중인 판에서 저장된 대결도 포함됩니다."
    )

    if st.button("🔄 분석 결과 다시 불러오기", key="refresh_analysis"):
        st.rerun()

    try:
        rows = load_all_duels()
    except Exception:
        st.error(
            "기록 조회에 실패했습니다. Supabase 연결 정보, "
            "테이블 권한 및 네트워크 상태를 확인한 뒤 다시 불러와 주세요."
        )
        return

    # 조회 성공 후 데이터가 없는 경우와 조회 실패를 구분
    if not rows:
        st.info(
            "아직 저장된 대결 기록이 없습니다. "
            "첫 번째 대결 결과가 저장되면 이 화면에서 확인할 수 있습니다."
        )
        st.caption(
            "기록 수는 참여 인원 수와 다릅니다. "
            "진행 중인 판에서 남긴 대결도 집계 대상입니다."
        )
        return

    df = analyze_duels(rows)

    # 전체 기록 수와 판 수
    game_count = len({
        row["game_id"]
        for row in rows
        if row.get("game_id") is not None
    })

    metric1, metric2 = st.columns(2)

    with metric1:
        st.metric("집계한 대결 기록 수", f"{len(rows):,}건")

    with metric2:
        st.metric("집계한 판 수", f"{game_count:,}판")

    st.caption(
        "대결 기록 수는 참여 인원 수가 아닙니다. "
        "진행 중인 판에서 저장된 대결도 집계에 포함됩니다."
    )

    # 표 표시용 승률 문자열
    display_df = df.copy()
    display_df["승률"] = display_df["승률"].apply(
        lambda value: f"{value:.1f}%"
        if pd.notna(value)
        else "아직 알 수 없음"
    )

    st.markdown("### 반찬별 성적표")
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 승률 비교")

    # 승률이 계산 가능한 반찬과 기록이 없는 반찬을 구분
    chart_df = df[df["승률"].notna()].copy()

    if chart_df.empty:
        st.info(
            "아직 승률을 계산할 수 있는 대결 기록이 없습니다. "
            "대결에 등장한 반찬이 생기면 그래프가 표시됩니다."
        )
    else:
        chart_df = chart_df.sort_values(
            "승률", ascending=True
        )

        fig = px.bar(
            chart_df,
            x="승률",
            y="반찬",
            orientation="h",
            text=chart_df["승률"].map(lambda value: f"{value:.1f}%"),
            labels={
                "승률": "승률 (%)",
                "반찬": "반찬",
            },
            title="반찬별 승률",
        )

        fig.update_traces(
            textposition="outside",
            cliponaxis=False,
        )
        fig.update_layout(
            xaxis=dict(
                range=[0, 110],
                ticksuffix="%",
            ),
            yaxis_title="",
            xaxis_title="승률 (%)",
            height=450,
            margin=dict(l=20, r=60, t=60, b=30),
        )

        st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "대결 수는 왼쪽·오른쪽 반찬에 등장한 횟수를 모두 합산합니다. "
        "승률은 승리 수 ÷ 대결 수 × 100이며, "
        "우승 횟수는 결승전 승리 기록만 집계합니다."
    )


# =====================================
# 화면 전환
# =====================================
game_tab, analysis_tab = st.tabs(
    ["🎮 월드컵 진행", "📊 전체 기록 분석"]
)

with game_tab:
    show_game()

with analysis_tab:
    show_analysis()
