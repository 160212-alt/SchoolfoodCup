import random
import uuid

import streamlit as st
from supabase import create_client


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="급식 반찬 월드컵",
    page_icon="🍱",
    layout="centered",
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

ROUND_NAMES = {
    8: "8강",
    4: "4강",
    2: "결승",
}


# --------------------------------------------------
# Supabase 연결
# --------------------------------------------------
@st.cache_resource
def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    if not url or not key:
        raise ValueError("Supabase 접속 정보가 비어 있습니다.")

    return create_client(url, key)


# --------------------------------------------------
# 게임 상태 관리
# --------------------------------------------------
def start_game():
    menus = MENUS.copy()
    random.shuffle(menus)

    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.round_menus = menus
    st.session_state.round_winners = []
    st.session_state.duel_index = 0
    st.session_state.completed = False
    st.session_state.champion = None
    st.session_state.duel_locked = False
    st.session_state.save_error = False
    st.session_state.error_message = ""


def save_choice(winner):
    """저장 성공이 확인된 경우에만 다음 대결로 진행한다."""

    if st.session_state.duel_locked:
        return

    menus = st.session_state.round_menus
    duel_index = st.session_state.duel_index

    left_menu = menus[duel_index * 2]
    right_menu = menus[duel_index * 2 + 1]

    # 현재 대결의 실제 후보인지 검증
    if winner not in (left_menu, right_menu):
        return

    # DB 요청 도중 중복 선택을 막는다.
    st.session_state.duel_locked = True
    st.session_state.save_error = False

    round_name = ROUND_NAMES[len(menus)]

    payload = {
        "game_id": st.session_state.game_id,
        "round": round_name,
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    try:
        client = get_supabase_client()

        # 기존 menu_duels 표에 한 행만 추가한다.
        # id와 created_at은 DB 기본값에 맡긴다.
        response = (
            client.table("menu_duels")
            .insert(payload)
            .select(
                "id, game_id, round, left_menu, right_menu, winner"
            )
            .execute()
        )

        # 응답에 저장된 행이 실제로 반환되었는지 확인한다.
        rows = response.data

        if not isinstance(rows, list) or len(rows) != 1:
            raise RuntimeError("저장 결과 행을 확인할 수 없습니다.")

        saved = rows[0]

        expected = {
            "game_id": payload["game_id"],
            "round": payload["round"],
            "left_menu": payload["left_menu"],
            "right_menu": payload["right_menu"],
            "winner": payload["winner"],
        }

        if any(saved.get(k) != v for k, v in expected.items()):
            raise RuntimeError("저장된 대결 정보가 요청과 일치하지 않습니다.")

    except Exception:
        # 요청이 서버에 반영되었는지 불확실할 수도 있으므로
        # 자동 재시도하지 않고 선택을 잠근다.
        st.session_state.save_error = True
        st.session_state.error_message = (
            "대결 결과의 저장 여부를 확인할 수 없습니다. "
            "중복 기록을 방지하기 위해 재선택을 잠갔습니다. "
            "교사에게 확인을 요청해 주세요."
        )
        return

    # 저장 확인이 끝난 뒤에만 승자를 다음 라운드에 반영한다.
    st.session_state.round_winners.append(winner)
    st.session_state.duel_index += 1

    total_duels_in_round = len(menus) // 2

    if st.session_state.duel_index >= total_duels_in_round:
        winners = st.session_state.round_winners.copy()

        if len(menus) == 2:
            st.session_state.champion = winners[0]
            st.session_state.completed = True
        else:
            st.session_state.round_menus = winners
            st.session_state.round_winners = []
            st.session_state.duel_index = 0

    # 성공한 경우에만 다음 선택을 허용한다.
    st.session_state.duel_locked = False


# --------------------------------------------------
# 앱 화면
# --------------------------------------------------
st.title("🍱 급식 반찬 월드컵")
st.caption("오늘의 최애 급식 반찬을 골라 주세요!")
st.divider()

if "game_id" not in st.session_state:
    start_game()

# 우승 화면
if st.session_state.completed:
    st.balloons()
    st.subheader("🏆 오늘의 급식 월드컵 우승!")
    st.markdown(
        f"<h1 style='text-align:center;'>"
        f"{st.session_state.champion}</h1>",
        unsafe_allow_html=True,
    )
    st.success("총 7번의 선택이 모두 완료되었습니다.")

    if st.button("🔄 다시 시작", use_container_width=True):
        start_game()
        st.rerun()

# 저장 확인 실패 화면
elif st.session_state.save_error:
    st.error("결과 확인 필요")
    st.warning(st.session_state.error_message)
    st.info(
        "현재 판은 잠긴 상태입니다. 저장 여부를 교사가 확인한 후 "
        "새로고침이나 재시작 여부를 결정해 주세요."
    )

# 대결 화면
else:
    menus = st.session_state.round_menus
    duel_index = st.session_state.duel_index

    round_name = ROUND_NAMES[len(menus)]
    left_menu = menus[duel_index * 2]
    right_menu = menus[duel_index * 2 + 1]

    completed_before = (
        4 if len(menus) == 8
        else 4 + 2 if len(menus) == 4
        else 6
    )
    current_game_number = completed_before + duel_index + 1

    st.subheader(f"{round_name} · {duel_index + 1}번째 대결")
    st.progress(current_game_number / 7)
    st.caption(f"전체 {current_game_number}/7번째 선택")

    st.write("두 반찬 중 더 먹고 싶은 하나를 선택하세요!")

    left_col, right_col = st.columns(2, gap="medium")

    with left_col:
        st.markdown(
            "<div style='text-align:center; padding:22px 8px; "
            "border:1px solid #dddddd; border-radius:14px;'>"
            "<div style='font-size:38px;'>🍚</div>"
            f"<h3>{left_menu}</h3>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            f"❤️ {left_menu}",
            key=f"left_{st.session_state.game_id}_{current_game_number}",
            use_container_width=True,
            disabled=st.session_state.duel_locked,
        ):
            save_choice(left_menu)
            st.rerun()

    with right_col:
        st.markdown(
            "<div style='text-align:center; padding:22px 8px; "
            "border:1px solid #dddddd; border-radius:14px;'>"
            "<div style='font-size:38px;'>🍱</div>"
            f"<h3>{right_menu}</h3>"
            "</div>",
            unsafe_allow_html=True,
        )

        if st.button(
            f"❤️ {right_menu}",
            key=f"right_{st.session_state.game_id}_{current_game_number}",
            use_container_width=True,
            disabled=st.session_state.duel_locked,
        ):
            save_choice(right_menu)
            st.rerun()

    st.divider()
    st.caption(
        "선택 결과는 대결당 한 행으로 저장됩니다. "
        "이름, 학번, 비밀번호는 수집하지 않습니다."
    )

    if st.button("🔄 다시 시작", use_container_width=True):
        start_game()
        st.rerun()
