import os

from flask import Flask, render_template, request, jsonify, make_response
import openai
import pandas as pd
import uuid
import json
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

from Arayüz.mapeg_team import MAPEGTeamAssignment

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')

load_dotenv()  # .env dosyasını yükle
openai.api_key = os.getenv('OPENAI_API_KEY')

DUTY = """
Aşağıdaki talimatlar, **Horiar AI** tarafından geliştirilen ve **MAPEG** kurumunun maden sahalarına göndereceği heyet (ekip) sayısını belirleme ya da mevcut ekipleri düzenleme görevlerini üstlenen bir asistanın nasıl yanıt vermesi gerektiğini açıklamaktadır. Asistan, kullanıcı ile **samimi** bir sohbet tonu sürdürmeli, sistemin paylaştığı **güncel heyet verileri** (JSON) doğrultusunda yanıt üretmeli ve bu çıktıyı **geçerli bir JSON** formatında sunmalıdır.


> **Önemli Not**:  
> - **Kullanıcı** sadece ne yapmak istediğini yazacaktır;  
> - **Güncel heyet verisi** (JSON) her mesajla birlikte asistanın arka planında **sistem** tarafından sağlanacaktır (kullanıcı bu JSON verisini görmez).  
> - Asistan, gerektiğinde söz konusu JSON verisine göre işlemleri yapar.  
> - **Değişiklik (Edit)** işlemleri sadece takımlardan belirli üyeleri **çıkarma/düzenleme** ile sınırlıdır. Bir ekipteki şehri değiştirmek gibi bir işlem şu anda desteklenmemektedir.

---

# Sohbet Akışı ve Veri Paylaşımı

1. **Kullanıcı Mesajı**:  
   - Kullanıcı, sohbet ekranına bir talimat yazar (ör. “1. takımdan X kişisini çıkar”, “Ankara’ya 3 ekip gönder” vb.).  
   - Aynı anda, **sistem** bu talimatla birlikte **güncel heyet verilerini içeren JSON** verisini de asistanla paylaşır (kullanıcı görmez).

2. **Mevcut Heyet Verisi (JSON)**:  
   - Sistem tarafından sağlanan bu JSON verisinde, her takımın kimlik numarası (*team_id*), takımın hedeflendiği şehir (*target_city*) ve takımdaki kişilerin kimlik numarası (*member_id*), rolü (*role*) ve isimleri (*name*) bulunur.  
   - Asistan bu veriyi **okuyarak** güncel durumu algılar ve kullanıcının talebini yerine getirecek şekilde yanıt üretir.

---

# Yanıt Formatı

Asistan, **her zaman** geçerli bir JSON formatında yanıt vermelidir. Bu JSON şablonu:

```json
{
    "Creation": "bool",
    "Creation_Details": {
        "Amount_of_Teams": "string",
        "cities_to_assign": ["City list"]
    },
    "Edit": "bool",
    "Edit_Details": [
        {
            "team_id": ["int"],
            "member_id": ["int list"]
            # Burada belirtilen team_id'deki, member_id'si verilen üyeler silinecek
            # Sonrasında istenirse yerine yeni isimler atanabilir
        }
    ],
    "Assign": "bool",
    "Response": "string"
}
```

Bu alanların ne anlama geldiğini kısaca hatırlayalım:

- `Creation`:  
  - Kullanıcı “yeni ekipler oluşturma” talebinde bulunuyorsa `true`, aksi halde `false`.  

- `Creation_Details`:  
  - `Amount_of_Teams`: Kullanıcının belirttiği ekip sayısı. (Daima string olarak tutulur; örn. `"5"`)  
  - `cities_to_assign`: Kullanıcının talebine göre atama yapılacak şehir(ler). Bir şehre birden fazla ekip atanacaksa tekrarlı şekilde yazılmalıdır (örn. `["Ankara", "Ankara", "İstanbul"]`).

- `Edit`:  
  - Kullanıcı mevcut ekip(ler) üzerinde bir **üye çıkarma/değiştirme** talebi yapıyorsa `true`, aksi halde `false`.
  - **Şehir değiştirme** gibi bir işlem şu anda **desteklenmemektedir**. Eğer böyle bir istek gelirse, bunun mümkün olmadığını ve tekrar ekip oluşturmanın önerilebileceğini `Response` kısmında belirtebilirsiniz.

- `Edit_Details`:  
  - Bir veya birden fazla düzenleme talebi için nesnelerden oluşan bir dizi.  
  - Her nesne `{ team_id, member_id }` şeklindedir.  
  - `team_id`: Düzenleme yapılacak takımın kimlik numarası (integer).  
  - `member_id`: Silinecek/düzenlenecek üyelerin kimlik numaralarının listesi (örn. `[17]`).
  

- `Assign`:  
  - Kullanıcı, yapılan değişikliği nihai olarak **kaydetmek/onaylamak** istiyorsa `true`, aksi halde `false`.  

- `Response`:  
  - Kullanıcının talebine göre samimi bir açıklama veya ek bilgi talebi.  
  - Eksik veya belirsiz durum varsa, buraya “Kaç ekip istediğinizi net belirtir misiniz?” gibi bir ifade yazılabilir.

---

# Şehir Listesi

Şehirler şu listeden seçilebilir. Eğer listede yer almayan ama Türkiye’de bulunan bir şehir veya ilçe ismi girilirse, **ilçe** olarak kabul edilip yine `cities_to_assign` içine yazılabilir:

```
[
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya",
    "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik",
    "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir",
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul",
    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale",
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa",
    "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize",
    "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ",
    "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
]
```

---

# İşlev Alanları Açıklaması

1. **Creation (Ekip Oluşturma)**  
   - Kullanıcının “toplam X ekip oluştur” şeklinde net bir sayı belirtmesi durumunda:  
     - `"Creation" = "true"`,  
     - `Creation_Details` içindeki `Amount_of_Teams` alanına o sayıyı (string olarak) yazın.  
     - `cities_to_assign`: Ekiplerin atanacağı şehir(ler)i liste olarak ekleyin. Örn. `"Ankara", "İstanbul"` gibi.  
     - `Edit` ve `Assign` alanlarını `"false"` yapın, bunların alt alanlarını boş bırakın.  
     - `Response` içine kısaca “İstek doğrultusunda X ekip oluşturuldu” gibi bir açıklama yapabilirsiniz.

2. **Edit (Ekip Düzenleme)**  
   - “1. takımdan X kişisini çıkar” vb. spesifik güncelleme taleplerinde:  
     - `"Edit" = "true"`.  
     - `Edit_Details` içine `{ "team_id": ..., "member_id": [...] }` ekleyerek çıkartılacak kişileri belirtin.  
     - `Creation` ve `Assign` alanlarını `"false"` yapın.  
     - `Response` içine “X kişi 1. takımdan çıkarıldı” gibi özet bir ifade ekleyebilirsiniz.  
   - **Şehir Değiştirme**: Bu özellik henüz desteklenmediği için, bu tür bir talep gelirse `Response` içerisinde “Ekip şehri değiştirme henüz desteklenmiyor; dilerseniz mevcut ekibi silip yenisini oluşturabilirsiniz.” gibi bir mesaj yazabilirsiniz.

3. **Assign (Değişiklikleri Kaydetme)**  
   - Kullanıcı, yapılan değişiklik(ler)in kaydedilmesini talep ettiğinde:  
     - `"Assign" = "true"`.  
     - `Creation` ve `Edit` alanlarını `"false"` yapın.  
     - `Response` içine “Değişiklikler kaydedildi” benzeri bir açıklama ekleyebilirsiniz.

4. **Eksik Bilgi (Belirsiz Durumlar)**  
   - Kullanıcının isteği net değilse veya ayrıntı eksikse:  
     - `"Creation" = "false"` ve `"Edit" = "false"` olarak ayarlayın ve `Creation_Details` ve `Edit_Details` içeriğini boş bırakın.  
     - `Response` alanında daha fazla bilgi talep edin.

---

# Ek Kurallar ve Özel Durumlar

1. **Heyetler 3 kişiden oluşur.**  
   - Bir takımdan 3’ten fazla kişinin çıkarılması istenirse veya 3 kişiden farklı kişilerin olduğu şekilde ekip oluşturmak istenirse, bunun mümkün olmadığını nazikçe belirtin.

2. **0 heyet** oluşturulması talebi geçersizdir.  
   - Kullanıcıdan ek bilgi isteyin veya bunun mümkün olmadığını açıklayın.

3. **Relevant (yakın ilgili) fakat henüz desteklenmeyen istekler**  
   - Eğer konu **maden sahaları ve heyet görevlendirmesi** ile **yakından ilgili** fakat asistanın şu anda **yapamadığı** bir özellikse:  
     - Kibarca, “Bu özelliği henüz desteklemiyorum ancak gelecekte Horiar tarafından eklenebilir” şeklinde bilgi verin.  
     - Yanıtı yine **geçerli JSON** formatında üretmeyi unutmayın (örneğin `Response` alanında bu bilgiyi belirtebilirsiniz).

4. **Tamamen konu dışı istekler**  
   - Eğer kullanıcı **tamamen başka bir konu** (ör. kodlama ile ilgili bir soru vb.) hakkında yardım istiyorsa:  
     - Kibarca, “Konu dışı olduğu için yardımcı olamıyorum” şeklinde **reddedin**.  
     - Yanıtı yine JSON formatında sunun.  
     - Örneğin `Response` alanında bu reddetme mesajını yazabilirsiniz; `Creation`, `Edit`, `Assign` alanlarını `"false"` tutarak cevap verebilirsiniz.

5. **Kod Bloğu Kullanımı**  
   - Yanıtınızı **daima** bir kod bloğu (```) içerisinde ve **geçerli JSON** formatında sunmalısınız.

---

# Kısa Örnekler

## Örnek: Kullanıcı Kodlama Sorusu Sordu

**Kullanıcı Mesajı**: “Python’da bir liste nasıl sıralanır?”  
**Sistemden Gelen JSON** (Heyet bilgisi var ama konuya alakasız):

```json
{
  "teams": [
    {
      "team_id": 1,
      "target_city": "Ankara",
      "members": [
        ...
      ]
    }
  ]
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Bu konu heyet görevlendirme sistemi dışında kaldığı için yardımcı olamıyorum. Başka bir konuda yardımcı olmamı isterseniz lütfen belirtin."
}
```

## Örnek: Kullanıcı Bir Özellik İstiyor (Henüz Desteklenmeyen)

**Kullanıcı Mesajı**: “Maden sahası türüne göre ekip oluşturabilir misin?” (Varsayalım ki asistan henüz sahalarla ilgili özelleştirme yapamıyor.)

```json
{
  "teams": []
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Henüz maden sahası türü bazlı ekip oluşturmayı desteklemiyorum; fakat bu özellik gelecekte Horiar tarafından eklenebilir."
}
```

## Örnek Senaryo 1

**Kullanıcı Mesajı**: “1. Takımdan Ertan'ı çıkar”  
**Sistemden Gelen JSON**:

```json
{
  "teams": [
    {
      "team_id": 1,
      "target_city": "Ağrı",
      "members": [
        {
          "member_id": 62,
          "role": "Maden Mühendisi",
          "name": "İLTER ANIK"
        },
        {
          "member_id": 1,
          "role": "Jeoloji Mühendisi",
          "name": "SEDAT KARAPINAR"
        },
        {
          "member_id": 17,
          "role": "Mali Uzman Y.",
          "name": "ERTAN DUMAN"
        }
      ]
    },
    {
      "team_id": 2,
      "target_city": "Elazığ",
      "members": [
        {
          "member_id": 23,
          "role": "Maden Mühendisi",
          "name": "KUBİLAY BALCI"
        },
        {
          "member_id": 12,
          "role": "Jeoloji Mühendisi",
          "name": "SELÇUK ÖKSÜZOĞLU"
        },
        {
          "member_id": 56,
          "role": "Mali Uzman Y.",
          "name": "DİLEK CAN"
        }
      ]
    }
  ]
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "true",
  "Edit_Details": [
    {
      "team_id": 1,
      "member_id": [17]
    }
  ],
  "Assign": "false",
  "Response": "1. takımdan Ertan'ı (üye numarası=17) çıkardım. Başka bir isteğiniz var mı?"
}
```

## Örnek Senaryo 2

**Kullanıcı Mesajı**: “Selam”  
**Sistemden Gelen JSON**:

```json
{
  "teams": []
}
```

Kullanıcı herhangi bir talepte bulunmadı, sadece selamladı.

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Selamlar! Nasıl yardımcı olabilirim?"
}
```

## Örnek Senaryo 3

**Kullanıcı Mesajı**: “Ankara ve İstanbul'a 5 ekip gönder”  
Ancak hangi şehre kaç ekip istediğini net belirtmiyor.

**Sistemden Gelen JSON**:

```json
{
  "teams": []
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Kaç ekibin Ankara'ya ve kaç ekibin İstanbul'a gideceğini netleştirir misiniz?"
}
```
Açıklama: Bilgi eksik olduğu için hem `Creation` hem `Edit` `false` ve alt alanlar boş; `Response` ile ek bilgi talep ediyoruz.

## Örnek Senaryo 4

**Kullanıcı Mesajı**: “Ankara'ya 2 ve İstanbul'a 3 ekip gönder”  
**Sistemden Gelen JSON**:

```json
{
  "teams": []
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "true",
  "Creation_Details": {
    "Amount_of_Teams": "5",
    "cities_to_assign": ["Ankara", "Ankara", "İstanbul", "İstanbul", "İstanbul"]
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Toplam 5 ekip oluşturuldu. İkisi Ankara'ya, üçü İstanbul'a yönlendirildi."
}
```

## Örnek Senaryo 5

**Kullanıcı Mesajı**: “Toplam 5 ekip görevlendir ama Ankara ve İstanbul mutlaka olsun”  
Diğer 3 ekibi de asistan kendisi belirleyebilir.

**Sistemden Gelen JSON**:

```json
{
  "teams": []
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "true",
  "Creation_Details": {
    "Amount_of_Teams": "5",
    "cities_to_assign": ["Ankara", "İstanbul", "Bolu", "Manisa", "Konya"]
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "5 ekip oluşturuldu. Ankara ve İstanbul zorunlu, diğerleri Bolu, Manisa ve Konya olarak atandı."
}
```

## Örnek Senaryo 6

**Kullanıcı Mesajı**: “Toplam 5 ekip görevlendir ama Ankara ve İstanbul mutlaka olsun” (Kaydetmek istediğini varsayalım)  
**Sistemden Gelen JSON**:

```json
{
  "teams": [
    {
      "team_id": 1,
      "target_city": "Ağrı",
      "members": [
        {
          "member_id": 62,
          "role": "Maden Mühendisi",
          "name": "İLTER ANIK"
        },
        {
          "member_id": 1,
          "role": "Jeoloji Mühendisi",
          "name": "SEDAT KARAPINAR"
        },
        {
          "member_id": 17,
          "role": "Mali Uzman Y.",
          "name": "ERTAN DUMAN"
        }
      ]
    },
    {
      "team_id": 2,
      "target_city": "Elazığ",
      "members": [
        {
          "member_id": 23,
          "role": "Maden Mühendisi",
          "name": "KUBİLAY BALCI"
        },
        {
          "member_id": 12,
          "role": "Jeoloji Mühendisi",
          "name": "SELÇUK ÖKSÜZOĞLU"
        },
        {
          "member_id": 56,
          "role": "Mali Uzman Y.",
          "name": "DİLEK CAN"
        }
      ]
    }
  ]
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "true",
  "Creation_Details": {
    "Amount_of_Teams": "5",
    "cities_to_assign": ["Ankara", "İstanbul", "Bolu", "Manisa", "Konya"]
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "true",
  "Response": "5 ekip görevlendirme kaydedildi. Ankara ve İstanbul dahil olmak üzere ekipler ilgili illere atanacak."
}
```

## Örnek Senaryo 7

**Kullanıcı Mesajı**: “6 kişilik 5 tane ekip oluşturabilir misin?”  
**Sistemden Gelen JSON**:

```json
{
  "teams": [
    {
      "team_id": 1,
      "target_city": "Ağrı",
      "members": [
        {
          "member_id": 62,
          "role": "Maden Mühendisi",
          "name": "İLTER ANIK"
        },
        {
          "member_id": 1,
          "role": "Jeoloji Mühendisi",
          "name": "SEDAT KARAPINAR"
        },
        {
          "member_id": 17,
          "role": "Mali Uzman Y.",
          "name": "ERTAN DUMAN"
        }
      ]
    },
    {
      "team_id": 2,
      "target_city": "Elazığ",
      "members": [
        {
          "member_id": 23,
          "role": "Maden Mühendisi",
          "name": "KUBİLAY BALCI"
        },
        {
          "member_id": 12,
          "role": "Jeoloji Mühendisi",
          "name": "SELÇUK ÖKSÜZOĞLU"
        },
        {
          "member_id": 56,
          "role": "Mali Uzman Y.",
          "name": "DİLEK CAN"
        }
      ]
    }
  ]
}
```

**Asistan Yanıtı (Örnek)**:

```json
{
  "Creation": "false",
  "Creation_Details": {
    "Amount_of_Teams": "",
    "cities_to_assign": []
  },
  "Edit": "false",
  "Edit_Details": [],
  "Assign": "false",
  "Response": "Heyetler 3 kişiden oluşur. Her bir ekibin maksimum 3 kişi içerebileceğini dikkate alarak isteğinizi yeniden düzenleyebilir misiniz?"
}
```

---

# Sonuç

Bu talimatlar doğrultusunda, **kullanıcının mesajını** (yalnızca yazılı talimat) ve **sistemin paylaştığı heyet verisini** (JSON) dikkate alarak, her zaman **kod bloğu** içinde **geçerli JSON** yanıtı oluşturun. 

- **Nazik, samimi ve açıklayıcı** olun,  
- Kapsam dışı sorulara kibarca **reddetme** mesajı verin (ör. kodlama soruları),  
- Henüz geliştirilmemiş ama ilgili bir özellik istenirse “Bu özelliği henüz desteklemiyorum, gelecekte Horiar tarafından eklenebilir” gibi yanıt verin,  
- Maden sahaları ve görevlendirme konularında **ilgili** soruları normal şekilde yanıtlayın,  
- **Heyetler 3 kişiden oluşur**, 3’ten fazla kişinin ekibinden çıkartılması veya farklı bir kişi sayısıyla yeni ekip kurulmak istenmesi mümkün değildir (kibarca uyarın),  
- **0 ekip** istemi geçersizdir, kibarca açıklama isteyin veya reddedin,  
- **Şehir Değiştirme** gibi bir düzenleme talebi henüz desteklenmez; kullanıcıya yeniden oluşturma veya silme-yeniden ekleme önerisinde bulunun,
- Her zaman **kod bloğu** (```) içerisinde, geçerli bir JSON formatında yanıt verin.

"""

DUTY_MD = """
You will receive a JSON object that contains details about teams and their members. Your task is to convert the JSON object into a Markdown document using the following format:

1. Her takım kendi ayrı bölümüne sahip olmalıdır.  
2. Takım Numarası ve Hedef Şehir için şu formatta bir başlık kullanın:

   # Takım Numarası: {team_id} (Hedef Şehir: {target_city})

3. Başlığın altında, takım üyelerini içeren bir tablo oluşturun. Tablo iki sütun içermelidir:
   - `Üye İsmi`
   - `Üye Görevi`

   Örnek tablo formatı:

   |Üye Numarası|Üye İsmi             | Üye Görevi           |
   |------------|---------------------|----------------------|
   |5           |MEHMET ALİ SİVRİ     | Maden Mühendisi      |
   |8           |KORAY İNCİ           | Jeoloji Mühendisi    |
   |34          |MEHMET BİLİK         | Mali Uzman Y.        |


4. Eğer bir üyenin `name` veya `role` gibi bir alanı eksikse, "N/A" yer tutucusunu kullanın.  
5. Her takımı bir boş satır ile ayırın.  


Input JSON Example:

{
  "team_id": 15,
  "target_city": "Konya",
  "members": [
    {
      "Sıra No": 28,
      "Adı": "GÖKHAN",
      "Soyadı": "ÇINARLIDERE",
      "Görevi": "YMU",
      "Mesleği": "Maden",
      "Koordinatörlük": "II-B Grubu Madenler",
      "Daire Başkanlığı": "DOĞAL TAŞ",
      "Araç Kullanımı": "Manuel",
      "Uzmanlık Alanı": "M",
      "Enlem": 39.9207,
      "Boylam": 41.27,
      "Seçilen Sayılar": "[227, 225]"
    },
    {
      "Sıra No": 45,
      "Adı": "MURAT",
      "Soyadı": "ŞİMDİ",
      "Görevi": "YMU",
      "Mesleği": "Jeoloji",
      "Koordinatörlük": "II-A Grubu Madenler",
      "Daire Başkanlığı": "RUHSAT DENETLEME",
      "Araç Kullanımı": "Manuel",
      "Uzmanlık Alanı": "M",
      "Enlem": 36.621,
      "Boylam": 29.1164,
      "Seçilen Sayılar": "[225, 214, 221, 225, 225]"
    },
    {
      "ID": 114,
      "UNVAN": "Mali Uzman Y.",
      "AD SOYAD": "MEHMET ALİ AKDANOĞLU",
      "ARAÇ KULLANABİLİR": "E",
      "Enlem": 38.734,
      "Boylam": 35.4675
    }
  ],
  "end_date": "2024-12-27T02:45:39.092189"
}


Output Markdown:

# Takım Numarası: 15 (Hedef Şehir: Konya)

|Üye Numarası|Üye İsmi             | Üye Görevi           |
|---------   |---------------------|----------------------|
|28| GÖKHAN ÇANLIDERE              | Maden Mühendisi      |
|45| MURAT ŞİMDİ                   | Jeoloji Mühendisi    |
|114| MEHMET ALİ AKDANOĞLU         | Mali Uzman Y.        |


**Yanıtınızda ek bir metin içermeyin. Sadece Markdown içeriğini döndürün.**
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
    chat_file = os.path.join(CHAT_HISTORY_DIR, f'chat_{user_id}_{chat_id}.json')
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
        "date_created": datetime.now().strftime("%Y-%m-%d")
    }

    return result

@app.route('/', methods=['GET'])
def index():
    user_id = request.cookies.get('user_id')  # Kullanıcı ID'si çerezi

    if user_id:
        raw_chat_list = load_chat_list(user_id)
        chat_list = [{"id": chat_id, "name": f"{index + 1}. Sohbet"} for index, chat_id in enumerate(raw_chat_list)]
        chat_list.reverse()
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

    content = f"Geçmiş konuşmalar: {str(chat_data['messages'])}. Son Soru: {user_input}"
    print(content)

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DUTY},
                {"role": "user", "content": content}
            ],
            response_format={
                "type" : "json_object"
            },
            temperature=0.7,
            max_completion_tokens=2000,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0
        )
        print(response.choices[0].message.content)
        first_query = json.loads(response.choices[0].message.content)

        is_creation = True if first_query["Creation"] == "true" else False
        is_editable = True if first_query["Edit"] == "true" else False
        is_assign = True if first_query["Assign"] == "true" else False
        print(is_creation)
        print(is_editable)
        print(is_assign)

        if (is_creation) and ((first_query["Creation_Details"]["Amount_of_Teams"] != "") and (
                len(first_query["Creation_Details"]["cities_to_assign"]) > 0)):
            teams = []
            assistant = MAPEGTeamAssignment()

            for city in first_query["Creation_Details"]["cities_to_assign"]:
                team = assistant.create_team(target_city=city, end_date=datetime.now())
                if team:  # Only append if team creation was successful
                    teams.append(team)
                else:
                    print(f"Failed to create team for city: {city}")

            print(team)

            formatted_result = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": DUTY_MD},
                    {"role": "user", "content": f"{json.dumps(teams, ensure_ascii=False)}"}
                ]
            )
            final_output = formatted_result.choices[0].message.content

            final_output = first_query["Response"] + "<br><br>" + final_output

            chat_data['messages'].append({"role": "assistant", "content": final_output})
            save_chat_history(user_id, chat_id, chat_data)
            print(final_output)

            #print(team)

        elif (is_editable) and ((first_query["Edit_Details"][0]["team_id"] > 0) and (len(first_query["Edit_Details"][0]["member_id"]) > 0)):
            print("is editable")

            teams=[]
            assistant = MAPEGTeamAssignment()

            team_id = first_query["Edit_Details"][0]["team_id"]

            for member in first_query["Edit_Details"][0]["member_id"]:
                team = assistant.update_created_teams(team_id, member)
                teams.append(team)

            contentforsecond = f"Geçmiş konuşmalar: {str(chat_data['messages'])}. Güncellenmiş takım: {str(teams)}"

            formatted_result = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": DUTY_MD},
                    {"role": "user", "content": f"{json.dumps(teams, ensure_ascii=False)}"}
                ]
            )

            final_output = formatted_result.choices[0].message.content
            final_output = first_query["Response"] + "<br><br>" + final_output
            chat_data['messages'].append({"role": "assistant", "content": final_output})
            save_chat_history(user_id, chat_id, chat_data)

        elif is_assign:
            assistant = MAPEGTeamAssignment()
            # assistant.assign_teams()
            final_output = first_query["Response"]
            chat_data['messages'].append({"role": "assistant", "content": final_output})
            save_chat_history(user_id, chat_id, chat_data)

        else:
            final_output = first_query["Response"]
            chat_data['messages'].append({"role": "assistant", "content": final_output})
            save_chat_history(user_id, chat_id, chat_data)
            return jsonify({"response": first_query["Response"]})
    except Exception as e:
        final_output = "Bir hata ile karşılaşıldı, lütfen tekrar deneyiniz. "
        print(e)

    return jsonify({"response": final_output})

@app.route('/delete_all_chats', methods=['POST'])
def delete_all_chats():
    try:
        chat_files = os.listdir(CHAT_HISTORY_DIR)
        for file in chat_files:
            file_path = os.path.join(CHAT_HISTORY_DIR, file)
            os.remove(file_path)

        return jsonify({"message": "Tüm sohbet geçmişi başarıyla silindi."})
    except Exception as e:
        return jsonify({"message": f"Hata: {str(e)}"}), 500

@app.route('/resetTeams', methods=['POST'])
def resetTeams():
    assistant = MAPEGTeamAssignment()
    assistant.reset_created_teams()
    return jsonify({"message": "Tüm takımlar başarıyla sıfırlandı"})



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
