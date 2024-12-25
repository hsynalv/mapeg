import os

from flask import Flask, render_template, request, jsonify, make_response
import openai
import pandas as pd
import uuid
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')

load_dotenv()  # .env dosyasını yükle
openai.api_key = os.getenv('OPENAI_API_KEY')

DUTY = """
**Asistan**, "MAPEG" kurumu için maden sahalarına göndermek için oluşturulacak heyet sayısını belirlemenize yardımcı olmak amacıyla **Horiar AI** tarafından geliştirilmiştir. Göreviniz, ihtiyaç duyulan heyet sayısını tespit etmek ve bunu yaparken samimi bir sohbet tonu korumaktır. Aşağıdaki talimatlara uyarak görevinizi yerine getiriniz.

---

## Yanıt Formatı ve Kurallar

Yanıtlarınızı **mutlaka** JSON formatında verin ve aşağıdaki kurallara uyun:

1. **Yeterlilik:**
   - Eğer kullanıcı, ihtiyaç duyulan heyet sayısını **net** bir şekilde belirtmişse:
     - `"Yeterlilik"` alanını `"true"` olarak ayarlayın.
     - `"Sayı"` alanına da kullanıcının belirttiği sayıyı yazın.
     - `"Yanıt"` alanı boş bir dize (`""`) olsun.
   - Eğer kullanıcı net bir sayı belirtmemiş ya da bilgi yetersizse:
     - `"Yeterlilik"` alanını `"false"` olarak ayarlayın.
     - `"Sayı"` alanına `0` yazın.
     - `"Yanıt"` alanına, kullanıcıdan göndermek istedikleri heyet sayısını dostça ve nazikçe tekrar soran bir metin yazın.

### Çıktı Formatı

Yanıt, aşağıdaki JSON yapısını içermelidir:


{
  "Yeterlilik": "bool",
  "Sayı": "int",
  "Yanıt": "string"
}


---

## Örnekler

**Örnek Kullanıcı Girdisi**:  
> 5 adet heyet gönderir misin?


{
  "Yeterlilik": True,
  "Sayı": 5,
  "Yanıt": ""
}


---

**Örnek Kullanıcı Girdisi**:  
> 12


{
  "Yeterlilik": True,
  "Sayı": "12",
  "Yanıt": ""
}


---

**Örnek Kullanıcı Girdisi**:  
> 0


{
  "Yeterlilik":False,
  "Sayı": 0,
  "Yanıt": "**0 heyet görevlendirmesi yapamayacağınızı belirtip kibarca tekrar sorun.**"
}


---

**Örnek Kullanıcı Girdisi**:  
> Selam


{
  "Yeterlilik": False,
  "Sayı": 0,
  "Yanıt": "**Kibarca selamlaşıp detay talep et.**"
}


---

## Notlar

- **0 heyet gönderilemeyeceği** için, kullanıcı bu talepte bulunursa mutlaka daha fazla bilgi isteyin.  
- Her zaman nazik ve samimi bir üslup kullanmaya özen gösterin.  
- Hem sayısal hem de sayısal olmayan girdileri doğru şekilde ayırt edip değerlendirin.  
- Yanıtınızı **her zaman** geçerli bir JSON biçiminde sunun.

"""

# Excel dosyalarının yolları
mali_uzmanlar_path = 'mali uzman ve harita mühendisi diğer.xlsx'
maden_uzmanlari_path = 'MEVCUT YERALTI MADEN UZMANLARI VE GÖREVLERİ düzenli fp.xlsx'

# Excel dosyalarını oku
mali_uzmanlar_df = pd.read_excel(mali_uzmanlar_path)
maden_uzmanlari_df = pd.read_excel(maden_uzmanlari_path)

# Mühendisleri filtrele
maden_uzmanlari_df['Mesleği'] = maden_uzmanlari_df['Mesleği'].str.strip()
maden_uzmanlari_df.columns = maden_uzmanlari_df.columns.str.strip()

maden_muhendisleri = maden_uzmanlari_df[maden_uzmanlari_df['Mesleği'] == 'Maden']
jeoloji_muhendisleri = maden_uzmanlari_df[maden_uzmanlari_df['Mesleği'] == 'Jeoloji']

mali_uzmanlari = mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Mali Uzman Y.']
harita_muhendisleri = mali_uzmanlar_df[mali_uzmanlar_df['UNVAN'] == 'Harita Mühendisi']

# Ekip oluşturma değişkenleri
created_teams = []
team_history = {}
pairing_history = {}
selected_members = set()
team_id_counter = 1
WAITING_PERIOD = timedelta(days=1)

# Türkiye'nin 81 ili
target_cities = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", "Ardahan", "Artvin",
    "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur",
    "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan",
    "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul",
    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale", "Kırklareli",
    "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Mardin", "Mersin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas",
    "Şanlıurfa", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
]

CHAT_HISTORY_DIR = 'chat_history'
CHAT_LIST_FILE = os.path.join(CHAT_HISTORY_DIR, 'chat_list.json')

# Klasörü oluştur
if not os.path.exists(CHAT_HISTORY_DIR):
    os.makedirs(CHAT_HISTORY_DIR)


def load_chat_list(user_id):
    user_chat_list_file = os.path.join(CHAT_HISTORY_DIR, f'chat_list_{user_id}.json')
    if os.path.exists(user_chat_list_file):
        with open(user_chat_list_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_chat_history(user_id, chat_id):
    print(f"user_id: {user_id}")
    print(f"chat_id: {chat_id}")
    chat_file = os.path.join(CHAT_HISTORY_DIR, f'chat_{user_id}_{chat_id}.json')
    print(chat_file)
    if os.path.exists(chat_file):
        with open(chat_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"messages": []}

def save_chat_history(user_id, chat_id, chat_data):
    chat_file = os.path.join(CHAT_HISTORY_DIR, f'chat_{user_id}_{chat_id}.json')
    with open(chat_file, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=4)

def save_chat_to_list(user_id, chat_id):
    chat_list = load_chat_list(user_id)
    if chat_id not in chat_list:
        chat_list.append(chat_id)

    user_chat_list_file = os.path.join(CHAT_HISTORY_DIR, f'chat_list_{user_id}.json')
    with open(user_chat_list_file, 'w', encoding='utf-8') as f:
        json.dump(chat_list, f, ensure_ascii=False, indent=4)

def create_team(team_id):
    global team_history, pairing_history, selected_members

    available_maden = maden_muhendisleri[~maden_muhendisleri['Sıra No'].isin(selected_members)]
    available_jeoloji = jeoloji_muhendisleri[~jeoloji_muhendisleri['Sıra No'].isin(selected_members)]
    available_mali = mali_uzmanlari[~mali_uzmanlari['ID'].isin(selected_members)]

    if available_maden.empty or available_jeoloji.empty or available_mali.empty:
        return None

    maden_muh = available_maden.sample(1).iloc[0]
    jeoloji_muh = available_jeoloji.sample(1).iloc[0]
    mali_uzman = available_mali.sample(1).iloc[0]

    team_members = [maden_muh['Sıra No'], jeoloji_muh['Sıra No'], mali_uzman['ID']]
    now = datetime.now()

    for member in team_members:
        if member not in team_history:
            team_history[member] = []
        team_history[member].append(now)

    selected_members.update(team_members)

    team = {
        "team_id": team_id,
        "target_city": random.choice(target_cities),
        "members": [
            {"role": "Maden Mühendisi", "name": f"{maden_muh['Adı']} {maden_muh['Soyadı']}"},
            {"role": "Jeoloji Mühendisi", "name": f"{jeoloji_muh['Adı']} {jeoloji_muh['Soyadı']}"},
            {"role": mali_uzman['UNVAN'], "name": mali_uzman['AD SOYAD']}
        ]
    }
    return team

def generate_teams(num_teams):
    global team_id_counter
    teams = []

    for _ in range(num_teams):
        team = create_team(team_id_counter)
        if team:
            teams.append(team)
            team_id_counter += 1
        else:
            break

    result = {
        "teams": teams,
        "total_teams": len(teams),
        "created_by": "Dil Modeli",
        "date_created": datetime.now().strftime("%Y-%m-%d")
    }

    return result


@app.route('/', methods=['GET'])
def index():
    user_id = request.cookies.get('user_id')  # Kullanıcı ID'si çerezi

    if user_id:
        chat_list = load_chat_list(user_id)
        response = make_response(render_template('index.html', chat_list=chat_list))
    else:
        response = make_response(render_template('index.html', chat_list=[]))
        user_id = str(uuid.uuid4())
        response.set_cookie('user_id', user_id, max_age=90 * 24 * 60 * 60)  # 3 ay


    chat_id = str(uuid.uuid4())
    response.set_cookie('chat_id', chat_id, max_age=90 * 24 * 60 * 60)  # 3 ay

    return response

# Yeni sohbet başlat
@app.route('/new_chat', methods=['POST'])
def new_chat():
    user_id = request.cookies.get('user_id')
    chat_id = request.cookies.get('chat_id')
    new_chat_id = str(uuid.uuid4())  # Yeni sohbet için UUID oluştur

    if not user_id:
        user_id = str(uuid.uuid4())  # Yeni kullanıcı için user_id oluştur

    save_chat_to_list(user_id, chat_id)  # Sohbet listesine ekle

    response = make_response(jsonify({"chat_id": new_chat_id}))
    response.set_cookie('chat_id', new_chat_id, max_age=90 * 24 * 60 * 60)
    response.set_cookie('user_id', user_id, max_age=90 * 24 * 60 * 60)
    return response

@app.route('/load_chat/<chat_id>', methods=['GET'])
def load_chat(chat_id):
    user_id = request.cookies.get('user_id')
    chat_data = load_chat_history(user_id, chat_id)

    response = make_response(jsonify({"chat_history": chat_data['messages']}))
    response.set_cookie("chat_id",chat_id)

    return response

@app.route('/generate', methods=['POST'])
def generate():
    user_input = request.form['prompt']
    chat_id = request.cookies.get('chat_id')
    user_id = request.cookies.get('user_id')

    if not user_id:
        user_id = str(uuid.uuid4())
        save_chat_to_list(user_id, chat_id)

    # Sohbet listesine eklenip eklenmediğini kontrol et
    save_chat_to_list(user_id, chat_id)  # Eğer listede yoksa ekler

    chat_data = load_chat_history(user_id, chat_id)
    chat_data['messages'].append({"role": "user", "content": user_input})

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DUTY},
                {"role": "user", "content": user_input}
            ]
        )
        model_output = json.loads(response.choices[0].message.content)
        is_available = bool(model_output.get("Yeterlilik"))

        if is_available:
            ekip_sayisi = int(model_output.get("Sayı"))
            result = generate_teams(ekip_sayisi)
            formatted_result = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Verilen JSON formatındaki ekip listesini HTML formatında aşağıdaki gibi düzenle:\n"
                                                 "Her ekibi madde işareti veya numaralandırma ile alt alta yaz. "
                                                 "Örneğin:\n"
                                                 "<ul>\n"
                                                 "<li><strong>Ekip 1 (Ankara)</strong><br>- Maden Mühendisi: Ahmet Özdemir<br>- Jeoloji Mühendisi: Mehmet Kanbur<br>- Mali Uzman: Ertan Duman</li>\n"
                                                 "<li><strong>Ekip 2 (İzmir)</strong><br>- Maden Mühendisi: Hasan Yılmaz<br>- Jeoloji Mühendisi: Murat Gürbüz<br>- Mali Uzman: Veli Demir</li>\n"
                                                 "</ul>"},
                    {"role": "user", "content": f"{json.dumps(result, ensure_ascii=False)}"}
                ]
            )
            final_output = formatted_result.choices[0].message.content
        else:
            final_output = model_output.get("Yanıt")

    except Exception as e:
        final_output = f"Hata: {str(e)}"

    chat_data['messages'].append({"role": "assistant", "content": final_output})
    save_chat_history(user_id, chat_id, chat_data)

    return jsonify({"response": final_output})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
