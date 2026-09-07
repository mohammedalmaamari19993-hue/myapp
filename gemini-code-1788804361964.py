import requests
import streamlit as st

# إعدادات الصفحة
st.set_page_config(
    page_title="مركز الأخبار اليومية",
    page_icon="📰",
    layout="wide",
)

# مفتاح الـ API الخاّص بـ NewsAPI
API_KEY = "2e2bf419d6b24706848ccccfd6d29f1e"

# تحسين مظهر الواجهة بـ CSS
st.markdown(
    """
    <style>
        .main { background-color: #0e1117; }
        .news-card {
            background-color: #1f293d;
            padding: 18px;
            border-radius: 12px;
            border: 1px solid #2e3b56;
            margin-bottom: 20px;
            height: 100%;
        }
        .news-title {
            font-size: 18px;
            font-weight: bold;
            color: #00f2fe;
            text-decoration: none;
            display: block;
            margin-bottom: 8px;
        }
        .news-title:hover { color: #4facfe; }
        .news-meta {
            font-size: 12px;
            color: #a0aec0;
            margin-bottom: 10px;
        }
        .news-desc {
            font-size: 14px;
            color: #e2e8f0;
            line-height: 1.5;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# --- الشريط الجانبي للتصفية والبحث ---
st.sidebar.title("📌 تصفح الأخبار")

# شريط البحث
search_query = st.sidebar.text_input("🔍 بحث عن موضوع معين:", "")

# اختيار الدول
countries = {
    "السعودية": "sa",
    "الإمارات": "ae",
    "مصر": "eg",
    "الولايات المتحدة": "us",
    "المملكة المتحدة": "gb",
}
selected_country = st.sidebar.selectbox("🌐 اختر الدولة:", list(countries.keys()))

# اختيار الأقسام
categories = {
    "عامة": "general",
    "تكنولوجيا": "technology",
    "أعمال واقتصاد": "business",
    "رياضة": "sports",
    "صحة": "health",
    "علوم": "science",
    "ترفيه": "entertainment",
}
selected_category = st.sidebar.selectbox("📂 اختر القسم:", list(categories.keys()))


# --- دالة جلب الأخبار ---
def get_latest_news(query="", country_code="sa", category_code="general"):
    if query:
        url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&apiKey={API_KEY}"
    else:
        url = f"https://newsapi.org/v2/top-headlines?country={country_code}&category={category_code}&apiKey={API_KEY}"

    try:
        res = requests.get(url, timeout=8)
        data = res.json()
        if data.get("status") == "ok":
            return data.get("articles", [])
        else:
            st.error(f"خطأ في جلب البيانات: {data.get('message')}")
            return []
    except Exception as e:
        st.error(f"تعذر الاتصال بالشبكة: {e}")
        return []


# --- الواجهة الرئيسية ---
st.title("📰 موقع الأخبار اليومية والعالمية")

if search_query:
    st.write(f"### نتائج البحث عن: **{search_query}**")
    articles = get_latest_news(query=search_query)
else:
    st.write(
        f"### أهم عناوين قسم **{selected_category}** - ({selected_country})"
    )
    articles = get_latest_news(
        country_code=countries[selected_country],
        category_code=categories[selected_category],
    )

if not articles:
    st.warning("لا توجد أخبار متاحة حالياً وفق الخيارات المحددة.")
else:
    # عرض الأخبار في أعمدة متجاورين
    for i in range(0, len(articles), 2):
        col1, col2 = st.columns(2)

        # الخبر الأول
        with col1:
            art = articles[i]
            st.markdown('<div class="news-card">', unsafe_allow_html=True)
            if art.get("urlToImage"):
                st.image(art["urlToImage"], use_container_width=True)
            st.markdown(
                f'<a class="news-title" href="{art["url"]}" target="_blank">{art["title"]}</a>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="news-meta">المصدر: {art["source"]["name"]} | {art.get("publishedAt", "")[:10]}</div>',
                unsafe_allow_html=True,
            )
            if art.get("description"):
                st.markdown(
                    f'<div class="news-desc">{art["description"]}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        # الخبر الثاني (إن وجد)
        if i + 1 < len(articles):
            with col2:
                art = articles[i + 1]
                st.markdown('<div class="news-card">', unsafe_allow_html=True)
                if art.get("urlToImage"):
                    st.image(art["urlToImage"], use_container_width=True)
                st.markdown(
                    f'<a class="news-title" href="{art["url"]}" target="_blank">{art["title"]}</a>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="news-meta">المصدر: {art["source"]["name"]} | {art.get("publishedAt", "")[:10]}</div>',
                    unsafe_allow_html=True,
                )
                if art.get("description"):
                    st.markdown(
                        f'<div class="news-desc">{art["description"]}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)