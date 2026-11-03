
import re
from itertools import combinations

import pandas as pd
import plotly.express as px
import streamlit as st


# 기본 설정
DATA_URL = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"

st.set_page_config(
    page_title="급식 규칙 찾기",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 급식 규칙 찾기")
st.caption("송탄고 중식 메뉴의 동시 출현 패턴과 연관 규칙을 분석합니다.")


# --------------------------------------------------
# 데이터 불러오기 및 전처리
# --------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv(DATA_URL, encoding="utf-8-sig")

    required_columns = {"날짜", "식사", "메뉴"}
    if not required_columns.issubset(df.columns):
        raise ValueError(
            "CSV에 필요한 열(날짜, 식사, 메뉴)이 모두 있는지 확인해 주세요."
        )

    # 메뉴 이름에서 괄호와 괄호 안의 내용 제거
    def clean_menu(menu):
        menu = str(menu).strip()
        menu = re.sub(r"\([^)]*\)|（[^）]*）", "", menu)
        return re.sub(r"\s+", " ", menu).strip()

    # 하루 식단을 하나의 거래로 처리
    df["메뉴목록"] = df["메뉴"].fillna("").apply(
        lambda value: sorted({
            cleaned
            for item in str(value).split("|")
            if (cleaned := clean_menu(item))
        })
    )

    # 메뉴가 없는 행 제외
    df = df[df["메뉴목록"].map(len) > 0].copy()

    return df


# --------------------------------------------------
# 연관 규칙 분석
# --------------------------------------------------
def make_rules(df):
    transactions = df["메뉴목록"].tolist()
    total_days = len(transactions)

    menu_counts = {}
    pair_counts = {}

    for menus in transactions:
        for menu in menus:
            menu_counts[menu] = menu_counts.get(menu, 0) + 1

        for menu_a, menu_b in combinations(sorted(set(menus)), 2):
            pair = (menu_a, menu_b)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    rules = []

    for (menu_a, menu_b), together_count in pair_counts.items():

        # 지지도
        support = together_count / total_days

        # A → B
        confidence_ab = together_count / menu_counts[menu_a]
        lift_ab = confidence_ab / (
            menu_counts[menu_b] / total_days
        )

        rules.append({
            "조건": menu_a,
            "결과": menu_b,
            "동시": together_count,
            "지지도": support,
            "신뢰도": confidence_ab,
            "향상도": lift_ab
        })

        # B → A
        confidence_ba = together_count / menu_counts[menu_b]
        lift_ba = confidence_ba / (
            menu_counts[menu_a] / total_days
        )

        rules.append({
            "조건": menu_b,
            "결과": menu_a,
            "동시": together_count,
            "지지도": support,
            "신뢰도": confidence_ba,
            "향상도": lift_ba
        })

    rules_df = pd.DataFrame(
        rules,
        columns=[
            "조건", "결과", "동시",
            "지지도", "신뢰도", "향상도"
        ]
    )

    return rules_df, menu_counts, pair_counts


# --------------------------------------------------
# 데이터 실행
# --------------------------------------------------
try:
    data = load_data()
    rules_df, menu_counts, pair_counts = make_rules(data)

except Exception as error:
    st.error("급식 데이터를 불러오거나 분석하는 중 오류가 발생했습니다.")
    st.exception(error)
    st.stop()


# --------------------------------------------------
# 요약 정보
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("급식 일수", f"{len(data):,}일")
col2.metric("메뉴 종류 수", f"{len(menu_counts):,}개")
col3.metric("함께 나온 메뉴 쌍 수", f"{len(pair_counts):,}쌍")

st.divider()


# --------------------------------------------------
# 연관 규칙 표
# --------------------------------------------------
st.subheader("📋 메뉴 연관 규칙")

control_col1, control_col2 = st.columns([2, 1])

with control_col1:
    selected_menu = st.selectbox(
        "메뉴 좁혀 보기",
        options=["전체 메뉴"] + sorted(menu_counts.keys()),
        index=0
    )

with control_col2:
    sort_option = st.selectbox(
        "정렬 기준",
        options=["향상도 순", "신뢰도 순", "동시 순"],
        index=0
    )


# 최소 동시 일수 슬라이더
min_together = st.slider(
    "최소 동시 일수",
    min_value=1,
    max_value=10,
    value=1,
    step=1
)


# 정렬 기준
sort_columns = {
    "향상도 순": ["향상도", "신뢰도", "동시"],
    "신뢰도 순": ["신뢰도", "향상도", "동시"],
    "동시 순": ["동시", "향상도", "신뢰도"]
}

filtered_rules = rules_df.copy()

# 메뉴 필터링
if selected_menu != "전체 메뉴":
    filtered_rules = filtered_rules[
        (filtered_rules["조건"] == selected_menu)
        | (filtered_rules["결과"] == selected_menu)
    ]

# 최소 동시 일수 필터링
filtered_rules = filtered_rules[
    filtered_rules["동시"] >= min_together
]

# 정렬
filtered_rules = filtered_rules.sort_values(
    by=sort_columns[sort_option],
    ascending=[False, False, False]
).reset_index(drop=True)


# 남은 규칙 개수 표시
st.write(
    f"**최소 동시 {min_together}일 이상: "
    f"{len(filtered_rules):,}개 규칙**"
)


# 표 출력
if filtered_rules.empty:
    st.info("조건에 맞는 연관 규칙이 없습니다.")

else:
    display_rules = filtered_rules.copy()

    display_rules["지지도"] = display_rules["지지도"].map(
        lambda value: f"{value:.2%}"
    )

    display_rules["신뢰도"] = display_rules["신뢰도"].map(
        lambda value: f"{value:.2%}"
    )

    display_rules["향상도"] = display_rules["향상도"].map(
        lambda value: f"{value:.3f}"
    )

    st.dataframe(
        display_rules,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# 향상도 상위 10개 그래프
# --------------------------------------------------
st.divider()
st.subheader("📊 향상도 상위 10개 규칙")

if filtered_rules.empty:
    st.info("그래프로 표시할 규칙이 없습니다.")

else:
    top_rules = filtered_rules.sort_values(
        by=["향상도", "신뢰도", "동시"],
        ascending=[False, False, False]
    ).head(10).copy()

    top_rules["규칙"] = (
        top_rules["조건"] + " → " + top_rules["결과"]
    )

    graph_data = top_rules.sort_values(
        "향상도",
        ascending=True
    )

    fig = px.bar(
        graph_data,
        x="향상도",
        y="규칙",
        orientation="h",
        text=graph_data["향상도"].map(
            lambda value: f"{value:.2f}"
        ),
        labels={
            "향상도": "향상도(Lift)",
            "규칙": "연관 규칙"
        },
        title="향상도 기준 상위 10개"
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False
    )

    fig.update_layout(
        height=max(400, 42 * len(top_rules) + 120),
        yaxis_title="",
        xaxis_title="향상도",
        margin=dict(
            l=20,
            r=60,
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

st.caption(
    "선택한 메뉴와 한 번도 같은 날 나오지 않았으며, "
    "혼자서는 10일 이상 등장한 메뉴를 찾습니다."
)

# 위의 메뉴 좁혀 보기와 별개의 선택 메뉴
negative_menu = st.selectbox(
    "함께 나온 적 없는 짝 찾기 - 메뉴 선택",
    options=sorted(menu_counts.keys()),
    index=0,
    key="negative_menu_select"
)

# 선택 메뉴의 등장 일수
selected_menu_days = menu_counts[negative_menu]

st.metric(
    f"'{negative_menu}'이(가) 나온 날",
    f"{selected_menu_days:,}일"
)

# 선택 메뉴와 함께 나온 적이 있는 메뉴 목록
appeared_with = set()

for menus in data["메뉴목록"]:
    if negative_menu in menus:
        appeared_with.update(menus)

# 자기 자신 제외
appeared_with.discard(negative_menu)

# 함께 나온 적 없는 메뉴 중 10일 이상 등장한 메뉴
never_together = []

for menu, count in menu_counts.items():
    if (
        menu != negative_menu
        and menu not in appeared_with
        and count >= 10
    ):
        never_together.append({
            "메뉴": menu,
            "나온 날": count
        })

never_df = pd.DataFrame(
    never_together,
    columns=["메뉴", "나온 날"]
)

if never_df.empty:
    st.info(
        "선택한 메뉴와 한 번도 함께 나오지 않았고 "
        "10일 이상 등장한 메뉴가 없습니다."
    )

else:
    never_df = never_df.sort_values(
        by="나온 날",
        ascending=False
    ).reset_index(drop=True)

    st.write(
        f"**함께 나온 적 없는 메뉴: {len(never_df):,}개**"
    )

    st.dataframe(
        never_df,
        use_container_width=True,
        hide_index=True
    )


# --------------------------------------------------
# 지표 설명
# --------------------------------------------------
with st.expander("📖 지지도·신뢰도·향상도란?"):

    st.markdown(
        """
        - **지지도**: 전체 급식일 중 두 메뉴가 함께 나온 날의 비율
        - **신뢰도**: 조건 메뉴가 나온 날 중 결과 메뉴도 함께 나온 비율
        - **향상도**: 두 메뉴의 연관 강도를 나타내는 값

        향상도 해석:
        - 1보다 크면 양의 연관성이 있습니다.
        - 1이면 서로 독립적으로 나타나는 수준입니다.
        - 1보다 작으면 음의 연관성이 있습니다.

        ※ 동시는 두 메뉴가 같은 날 함께 나온 횟수입니다.

        ※ 한 메뉴 쌍은 A → B와 B → A 두 규칙으로 표시됩니다.
        """
    )

st.caption("데이터 출처: 송탄고 중식 급식 CSV")

