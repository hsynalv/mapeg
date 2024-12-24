import os

from flask import Flask, render_template, request, jsonify
import openai
import pandas as pd
import numpy as np
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

app = Flask(__name__, template_folder='app/templates')

load_dotenv()  # .env dosyasını yükle
openai.api_key = os.getenv('OPENAI_API_KEY')

DUTY = """
Sen bir ekip oluşturma asistanısın. Kullanıcının belirttiği ekip sayısına göre ekipler oluşturuldu ve aşağıdaki formatta sana gönderildi:

{
  "teams": [
    {
      "team_id": 1,
      "target_city": "Ankara",
      "members": [
        {"role": "Maden Mühendisi", "name": "Ahmet Özdemir"},
        {"role": "Jeoloji Mühendisi", "name": "Mehmet Kanbur"},
        {"role": "Mali Uzman Y.", "name": "Seyfettin Özdemir"}
      ]
    }
  ],
  "total_teams": 1,
  "created_by": "Dil Modeli",
  "date_created": "2024-12-24"
}

Bu veriyi al ve kullanıcının anlayacağı düzenli bir şekilde her bir ekibi listele. Aşağıdaki formatı kullanarak cevabını hazırla:

Örnek:  
1. **Ekip 1 (Ankara)**  
- Maden Mühendisi: Ahmet Özdemir  
- Jeoloji Mühendisi: Mehmet Kanbur  
- Mali Uzman: Seyfettin Özdemir  

2. **Ekip 2 (İzmir)**  
- Maden Mühendisi: Veli Demir  
- Jeoloji Mühendisi: Hasan Yılmaz  
- Mali Uzman: Hakan Acar  

Eğer hiç ekip oluşturulmadıysa şu mesajı ver:  
"Uygun mühendis veya uzman bulunamadı. Lütfen tekrar deneyin."

Cevabın kullanıcı dostu ve düzenli olsun.

"""

# Excel dosyalarının yolları
mali_uzmanlar_path = 'E:/Projeler/Mapeg/demo/mali uzman ve harita mühendisi diğer.xlsx'
maden_uzmanlari_path = 'E:/Projeler/Mapeg/demo/MEVCUT YERALTI MADEN UZMANLARI VE GÖREVLERİ düzenli fp.xlsx'

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
WAITING_PERIOD = timedelta(days=10)
target_cities = ["Ankara", "İstanbul", "İzmir", "Bursa", "Antalya"]


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


# Prompt işleyen endpoint
@app.route('/generate', methods=['POST'])
def generate():
    user_input = request.form['prompt']

    try:
        # OpenAI'den ekip sayısını al
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Kullanıcının belirttiği ekip sayısını ver. Örnek: '5 ekip istiyorum' -> '5'"},
                {"role": "user", "content": user_input}
            ]
        )
        ekip_sayisi = int(response.choices[0].message.content.strip())

        # Algoritmayı çağır
        result = generate_teams(ekip_sayisi)

        # Oluşan ekip listesini dil modeline gönder
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

    except ValueError:
        final_output = "Lütfen geçerli bir ekip sayısı belirtin."
    except Exception as e:
        final_output = f"Hata: {str(e)}"

    return jsonify({"response": final_output})


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
