
import re
from itertools import combinations

import pandas as pd
import streamlit as st
import plotly.express as px


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍱",
    layout="wide"
)

DATA_URL = (
    "https://raw.githubusercontent.com/it-teacher-go/"
    "data-share-/main/songtan_meals_184.csv"
)

st.title("🍱 급식 규칙 찾기")
st.write(
    "송탄고 중식 184일의 급식 데이터를 분석해 "
    "메뉴 간의 연관 규칙을 찾아봅니다."
)


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_URL, encoding="utf-8")

    df.columns = df.columns.str.strip()

    required_columns = ["날짜", "식사", "메뉴"]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(
                f"CSV에 '{col}' 열이 없습니다."
            )

    df = df[required_columns].copy()
    df = df.dropna(subset=["메뉴"])

    return df


# --------------------------------------------------
# 메뉴 정리
# --------------------------------------------------

def clean_menu(menu):
    """
    메뉴명에서 괄호와 괄호 안의 내용을 제거합니다.
    예: 치킨(닭고기) -> 치킨
    """
    menu = str(menu)

    # 소괄호와 그 안의 내용 제거
    menu = re.sub(r"\([^)]*\)", "", menu)

    # 공백 정리
    menu = re.sub(r"\s+", " ", menu).strip()

    return menu


def make_transactions(df):
    transactions = []

    for menu_text in df["메뉴"]:

        menus = str(menu_text).split("|")

        cleaned = {
            clean_menu(menu)
            for menu in menus
            if clean_menu(menu)
        }

        # 하루를 하나의 장바구니로 취급
        transactions.append(sorted(cleaned))

    return transactions


# --------------------------------------------------
# 연관 규칙 계산
# --------------------------------------------------

def analyze_transactions(transactions):

    total_days = len(transactions)

    # 메뉴별 출현 일수
    menu_counts = {}

    # 메뉴 쌍별 동시 출현 일수
    pair_counts = {}

    for basket in transactions:

        for menu in basket:
            menu_counts[menu] = (
                menu_counts.get(menu, 0) + 1
            )

        for a, b in combinations(basket, 2):

            pair_counts[(a, b)] = (
                pair_counts.get((a, b), 0) + 1
            )

    rules = []

    # 관측된 메뉴 쌍을 대상으로 규칙 생성
    for (a, b), together in pair_counts.items():

        support_ab = together / total_days

        support_a = menu_counts[a] / total_days
        support_b = menu_counts[b] / total_days

        # A -> B
        confidence_ab = together / menu_counts[a]
        lift_ab = confidence_ab / support_b

        rules.append({
            "조건": a,
            "결과": b,
            "동시": together,
            "지지도": support_ab,
            "신뢰도": confidence_ab,
            "향상도": lift_ab
        })

        # B -> A
        confidence_ba = together / menu_counts[b]
        lift_ba = confidence_ba / support_a

        rules.append({
            "조건": b,
            "결과": a,
            "동시": together,
            "지지도": support_ab,
            "신뢰도": confidence_ba,
            "향상도": lift_ba
        })

    rules_df = pd.DataFrame(
        rules,
        columns=[
            "조건",
            "결과",
            "동시",
            "지지도",
            "신뢰도",
            "향상도"
        ]
    )

    return menu_counts, pair_counts, rules_df


# --------------------------------------------------
# 데이터 분석 실행
# --------------------------------------------------

try:

    df = load_data()

    transactions = make_transactions(df)

    menu_counts, pair_counts, rules_df = (
        analyze_transactions(transactions)
    )

except Exception as e:

    st.error(
        f"데이터를 불러오는 중 오류가 발생했습니다: {e}"
    )

    st.stop()


# --------------------------------------------------
# 요약 정보
# --------------------------------------------------

total_days = len(transactions)

menu_type_count = len(menu_counts)

pair_count = len(pair_counts)

st.subheader("📊 분석 요약")

st.markdown(
    f"""
    **급식 일수:** {total_days}일　|　
    **메뉴 종류 수:** {menu_type_count}개　|　
    **함께 나온 적이 있는 메뉴 쌍 수:** {pair_count}쌍
    """
)

st.divider()


# --------------------------------------------------
# 연관 규칙 탐색
# --------------------------------------------------

st.subheader("🔍 연관 규칙 탐색")

col1, col2 = st.columns(2)

with col1:

    sort_option = st.selectbox(
        "정렬 기준",
        ["향상도 순", "신뢰도 순", "동시 순"]
    )

with col2:

    selected_menu = st.selectbox(
        "연관 규칙 좁혀 보기",
        ["전체 메뉴"] + sorted(menu_counts.keys())
    )


# --------------------------------------------------
# 최소 동시 일수 슬라이더
# --------------------------------------------------

min_together = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1,
    help=(
        "두 메뉴가 함께 나온 일수가 "
        "선택한 값보다 적은 규칙은 제외합니다."
    )
)


# --------------------------------------------------
# 규칙 필터링 및 정렬
# --------------------------------------------------

# 최소 동시 일수 필터
filtered_rules = rules_df[
    rules_df["동시"] >= min_together
].copy()

# 메뉴 필터
if selected_menu != "전체 메뉴":

    filtered_rules = filtered_rules[
        (filtered_rules["조건"] == selected_menu)
        | (filtered_rules["결과"] == selected_menu)
    ].copy()


# 정렬 기준
sort_columns = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시"
}

sort_column = sort_columns[sort_option]

filtered_rules = filtered_rules.sort_values(
    by=sort_column,
    ascending=False
).reset_index(drop=True)


# --------------------------------------------------
# 남은 규칙 수
# --------------------------------------------------

remaining_rules = len(filtered_rules)

st.markdown(
    f"**현재 표에 남은 규칙: {remaining_rules}개**"
)


# --------------------------------------------------
# 규칙 표
# --------------------------------------------------

st.subheader("📋 메뉴 연관 규칙")

if filtered_rules.empty:

    st.info(
        "조건에 맞는 연관 규칙이 없습니다. "
        "최소 동시 일수를 낮춰 보세요."
    )

else:

    display_rules = filtered_rules.copy()

    # 지지도와 신뢰도를 백분율로 표시
    display_rules["지지도"] = (
        display_rules["지지도"] * 100
    ).map(lambda x: f"{x:.2f}%")

    display_rules["신뢰도"] = (
        display_rules["신뢰도"] * 100
    ).map(lambda x: f"{x:.2f}%")

    display_rules["향상도"] = (
        display_rules["향상도"]
    ).map(lambda x: f"{x:.3f}")

    st.dataframe(
        display_rules[
            [
                "조건",
                "결과",
                "동시",
                "지지도",
                "신뢰도",
                "향상도"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# 향상도 상위 10개 그래프
# --------------------------------------------------

st.divider()

st.subheader("📈 향상도 상위 10개 규칙")

if filtered_rules.empty:

    st.info(
        "그래프로 표시할 규칙이 없습니다."
    )

else:

    top10 = (
        filtered_rules
        .sort_values("향상도", ascending=False)
        .head(10)
        .copy()
    )

    # 규칙 이름 생성
    top10["규칙"] = (
        top10["조건"] + " → " + top10["결과"]
    )

    # 향상도가 큰 규칙을 위에 표시
    top10 = top10.sort_values(
        "향상도",
        ascending=True
    )

    fig = px.bar(
        top10,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        labels={
            "향상도": "향상도 (Lift)",
            "규칙": "연관 규칙"
        },
        title="향상도 상위 10개 메뉴 규칙"
    )

    fig.update_traces(
        texttemplate="%{text:.3f}",
        textposition="outside"
    )

    fig.update_layout(
        height=max(400, len(top10) * 45),
        yaxis_title="",
        xaxis_title="향상도 (Lift)",
        margin=dict(
            l=20,
            r=80,
            t=60,
            b=30
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )


# --------------------------------------------------
# 함께 나온 적 없는 짝
# --------------------------------------------------

st.divider()

st.subheader("🚫 함께 나온 적 없는 짝")

st.write(
    "선택한 메뉴와 같은 날 한 번도 함께 나오지 않았지만, "
    "혼자서는 10일 이상 등장한 메뉴를 찾아봅니다."
)

# 기존 연관 규칙 필터와 별개로 작동하는 선택
selected_menu_for_absence = st.selectbox(
    "함께 나온 적 없는 짝을 찾을 기준 메뉴",
    sorted(menu_counts.keys()),
    key="absence_menu_selector"
)


# --------------------------------------------------
# 함께 나온 적 없는 메뉴 계산
# --------------------------------------------------

absence_menu = selected_menu_for_absence

absence_menu_days = menu_counts[absence_menu]

absence_results = []

for other_menu, other_days in menu_counts.items():

    # 자기 자신은 제외
    if other_menu == absence_menu:
        continue

    # 혼자서 10일 이상 나온 메뉴만 대상
    if other_days < 10:
        continue

    # 두 메뉴가 함께 나온 횟수 확인
    pair = tuple(sorted([absence_menu, other_menu]))

    together_days = pair_counts.get(pair, 0)

    # 한 번도 함께 나오지 않은 경우
    if together_days == 0:

        absence_results.append({
            "메뉴": other_menu,
            "출현 일수": other_days,
            "기준 메뉴 출현 일수": absence_menu_days,
            "동시 출현 일수": together_days
        })


# --------------------------------------------------
# 결과 표
# --------------------------------------------------

absence_df = pd.DataFrame(
    absence_results,
    columns=[
        "메뉴",
        "출현 일수",
        "기준 메뉴 출현 일수",
        "동시 출현 일수"
    ]
)

if absence_df.empty:

    st.info(
        f"'{absence_menu}'와 함께 나온 적이 없으면서 "
        "10일 이상 등장한 메뉴가 없습니다."
    )

else:

    absence_df = absence_df.sort_values(
        by="출현 일수",
        ascending=False
    ).reset_index(drop=True)

    st.markdown(
        f"**기준 메뉴 '{absence_menu}'의 출현 일수: "
        f"{absence_menu_days}일**"
    )

    st.markdown(
        f"**함께 나온 적 없는 메뉴: "
        f"{len(absence_df)}개**"
    )

    st.dataframe(
        absence_df,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# 지표 설명
# --------------------------------------------------

st.divider()

with st.expander("📖 연관 규칙 지표 알아보기"):

    st.markdown(
        """
        **지지도 (Support)**

        두 메뉴가 함께 나온 일수 ÷ 전체 급식 일수

        **신뢰도 (Confidence)**

        조건 메뉴가 나온 날 중 결과 메뉴도 나온 비율

        **향상도 (Lift)**

        신뢰도 ÷ 결과 메뉴의 전체 출현 비율

        - 향상도 > 1 : 두 메뉴가 우연히 독립적으로 나오는 것보다 자주 함께 나옴
        - 향상도 = 1 : 두 메뉴가 독립적으로 나타나는 것과 비슷함
        - 향상도 < 1 : 두 메뉴가 함께 나오는 경향이 적음

        **동시 출현 일수**

        두 메뉴가 같은 날 함께 나온 횟수입니다.

        예를 들어 A → B의 신뢰도가 80%라면,
        A가 나온 날의 80%에 B도 나왔다는 뜻입니다.
        """
    )
