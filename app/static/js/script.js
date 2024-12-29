const sidebar = document.querySelector("#sidebar");
const hide_sidebar = document.querySelector(".hide-sidebar");

hide_sidebar.addEventListener( "click", function() {
    sidebar.classList.toggle( "hidden" );
} );

    const form = document.getElementById('chatForm');
    const chatBox = document.getElementById('chatBox');
    const textarea = form.querySelector('textarea');

    // Form gönderildiğinde çalışacak ana işlem
    form.onsubmit = async (e) => {
        e.preventDefault();
        sendMessage();
    };

    // Enter tuşuna basıldığında formu gönder, Shift + Enter yeni satır ekler
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });

    // Mesaj gönderme işlevi
    async function sendMessage() {
    const formData = new FormData(form);
    const userInput = formData.get('prompt').trim();

    if (!userInput) {
        alert("Lütfen bir mesaj girin.");
        return;
    }

    // Kullanıcı mesajını ekle
    const userMessage = document.createElement('div');
    userMessage.className = 'message user-message';
    userMessage.textContent = userInput;
    chatBox.appendChild(userMessage);
    form.reset();

    // Yükleniyor animasyonu ekle
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'message ai-message loading';

    const dotsContainer = document.createElement('div');
    dotsContainer.className = 'loading-dots';
    dotsContainer.innerHTML = `
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
    `;
    loadingMessage.appendChild(dotsContainer);
    chatBox.appendChild(loadingMessage);

    try {
        // API'ye POST isteği gönder
        const response = await fetch('/generate', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        // Yükleniyor mesajını kaldır
        chatBox.removeChild(loadingMessage);

        // AI cevabını metin ve tablo olarak ayır ve ekle
        const parts = result.response.split("<br><br>");
        const messageText = parts[0];  // İlk kısım metin
        const tableMarkdown = parts.slice(1).join("<br><br>");  // Kalan kısım tablo (çoklu olabilir)

        // Metin mesajı ekle
        const aiText = document.createElement('div');
        aiText.className = 'message ai-message';
        aiText.innerHTML = messageText;
        chatBox.appendChild(aiText);

        // Markdown tablosunu HTML'e çevirip ekle
        if (tableMarkdown) {
            const table = markdownToHTML(tableMarkdown);
            chatBox.appendChild(table);
        }
    } catch (error) {
        chatBox.removeChild(loadingMessage);

        const errorMessage = document.createElement('div');
        errorMessage.className = 'message ai-message';
        errorMessage.textContent = "Bir hata oluştu. Lütfen daha sonra tekrar deneyin.";
        chatBox.appendChild(errorMessage);
    }

    // Sohbet kutusunu en alta kaydır
    chatBox.scrollTop = chatBox.scrollHeight;
}

    // Yeni Sohbet Başlatma
    async function startNewChat() {
        const response = await fetch('/new_chat', { method: 'POST' });
        const data = await response.json();
        location.reload();
    }

async function loadChat(chatId) {
    const response = await fetch(`/load_chat/${chatId}`);
    const result = await response.json();

    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = '';

    result.chat_history.forEach(message => {
        // AI mesajı mı kontrol et
        if (message.role === 'assistant') {
            const parts = message.content.split("<br><br>");
            const messageText = parts[0];  // İlk kısım metin
            const tableMarkdown = parts.slice(1).join("<br><br>");  // Kalan kısım tablo (çoklu olabilir)

            // Metin mesajı ekle
            const aiText = document.createElement('div');
            aiText.className = 'message ai-message';
            aiText.innerHTML = messageText;
            chatBox.appendChild(aiText);

            // Markdown tablosunu HTML'e çevirip ekle
            if (tableMarkdown) {
                const table = markdownToHTML(tableMarkdown);
                chatBox.appendChild(table);
            }
        } else {
            // Kullanıcı mesajı ise doğrudan ekle
            const msgContainer = document.createElement('div');
            msgContainer.className = 'message user-message';
            msgContainer.innerHTML = message.content;
            chatBox.appendChild(msgContainer);
        }
    });

    chatBox.scrollTop = chatBox.scrollHeight;
}



    async function deleteAllChats() {
        const confirmed = confirm("Tüm sohbetleri silmek istediğinize emin misiniz?");
        if (confirmed) {
            const response = await fetch('/delete_all_chats', { method: 'POST' });
            const result = await response.json();
            alert(result.message);
            location.reload();
        }
    }

    async function resetTeams() {
        const confirmed = confirm("Tüm takımları silmek istediğinize emin misiniz?");
        if (confirmed) {
            const response = await fetch('/resetTeams', { method: 'POST' });
            const result = await response.json();
            alert(result.message);
            location.reload();
        }
    }

   // API yanıtını alıp tabloya çevirme
function markdownToHTML(md) {
    const parts = md.split(/\n(?=# Takım Numarası)/g);  // Her Takım Numarası başlığından ayır
    const container = document.createElement('div');  // Tüm içerikleri barındıracak kapsayıcı

    parts.forEach(part => {
        const lines = part.trim().split("\n");
        const table = document.createElement('table');
        table.className = 'styled-table';

        let teamHeaderAdded = false;  // Takım başlığı eklendi mi kontrolü
        let headerRowAdded = false;  // Tablo başlığı sadece bir kez eklenmeli

        lines.forEach((line, index) => {
            if (line.startsWith("# Takım Numarası:")) {
                const header = document.createElement('h3');
                header.innerHTML = line.replace("# ", "");  // H3 başlığı olarak ekle
                container.appendChild(header);  // Takım başlığını ekle
                teamHeaderAdded = true;
            } else if (line.includes("|")) {
                const row = document.createElement('tr');
                const columns = line.split("|").slice(1, -1);  // İlk ve son boş sütunları çıkar

                columns.forEach((col, colIndex) => {
                    const cell = document.createElement(index === 1 ? 'th' : 'td');  // İlk satırsa th, diğerleri td
                    cell.textContent = col.trim();
                    row.appendChild(cell);
                });

                // Başlık satırını ekle
                if (index === 1 && !headerRowAdded) {
                    const thead = document.createElement('thead');
                    thead.appendChild(row);
                    table.appendChild(thead);
                    headerRowAdded = true;
                } else {
                    table.appendChild(row);
                }
            }
        });

        // Tabloları ekleyelim
        if (teamHeaderAdded) {
            container.appendChild(table);
            container.appendChild(document.createElement('br'));
        }
    });

    return container;
}