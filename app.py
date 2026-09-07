import streamlit as st
import requests

# إعدادات الصفحة الأساسية
st.set_page_config(
    page_title="تطبيق حالة الطقس",
    page_icon="🌤️",
    layout="centered"
)

# عنوان التطبيق
st.title("🌤️ تطبيق حالة الطقس (OpenWeatherMap)")
st.write("أدخل اسم المدينة باللغة العربية أو الإنجليزية للحصول على تفاصيل الطقس الحالية.")

# المفتاح الخاص بك لـ OpenWeatherMap API
API_KEY = "f7b522017aa91ebeb56bcf68f6008298"

# مدخل اسم المدينة
city = st.text_input("اسم المدينة:", placeholder="مثال: Cairo, Riyadh, London, Makkah")

# زر البحث
if st.button("عرض حالة الطقس", type="primary"):
    if city.strip() != "":
        # رابط API
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': API_KEY,
            'units': 'metric',
            'lang': 'ar'
        }
        
        try:
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if response.status_code == 200:
                city_name = data['name']
                country = data['sys']['country']
                temp = data['main']['temp']
                feels_like = data['main']['feels_like']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']
                description = data['weather'][0]['description']
                icon = data['weather'][0]['icon']
                
                st.success(f"تم جلب البيانات بنجاح لمدينة: **{city_name}، {country}**")
                
                # عرض تفاصيل الطقس بطريقة مرئية جذابة
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric(label="🌡️ درجة الحرارة الحالية", value=f"{temp} °C", delta=f"الشعور {feels_like} °C")
                    st.write(f"📝 **الحالة:** {description.capitalize()}")
                    st.image(f"http://openweathermap.org/img/wn/{icon}@2x.png", width=100)
                    
                with col2:
                    st.metric(label="💧 نسبة الرطوبة", value=f"{humidity} %")
                    st.metric(label="💨 سرعة الرياح", value=f"{wind_speed} م/ث")
                    
            elif response.status_code == 404:
                st.error(f"❌ لم يتم العثور على المدينة '{city}'. يرجى التأكد من كتابة الاسم بشكل صحيح.")
            elif response.status_code == 401:
                st.error("❌ مفتاح API غير صالح أو لم يتم تفعيله بعد.")
            else:
                st.error(f"❌ حدث خطأ غير متوقع (رمز الخطأ: {response.status_code}).")
                
        except Exception as e:
            st.error(f"❌ تعذر الاتصال بالخدمة: {e}")
    else:
        st.warning("⚠️ يرجى إدخال اسم المدينة أولاً!")
