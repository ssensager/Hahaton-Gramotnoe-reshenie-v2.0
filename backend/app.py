from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с React

# Конфигурация для загрузки файлов
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Создаём папку для загрузок, если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================
# СЕКЦИЯ ДЛЯ ИНТЕГРАЦИИ LLM МОДЕЛИ
# ============================================

class DocumentAnalyzer:
    """
    Базовый класс для анализа документов.
    Ваш друг должен реализовать методы ниже со своей LLM моделью.
    """
    
    def __init__(self):
        # TODO: Инициализация модели
        # Например:
        # self.model = load_model('path_to_model')
        # self.tokenizer = load_tokenizer('path_to_tokenizer')
        pass
    
    def analyze_document(self, file_path, file_type):
        """
        Анализирует загруженный документ.
        
        Args:
            file_path: путь к файлу
            file_type: тип файла (pdf, txt, etc.)
        
        Returns:
            dict: результат анализа с ключевой информацией
        """
        # TODO: Реализовать извлечение текста из документа
        # Для PDF: использовать PyPDF2 или pdfplumber
        # Для изображений: использовать OCR (pytesseract)
        # Для Word: использовать python-docx
        
        extracted_text = self._extract_text(file_path, file_type)
        
        # TODO: Реализовать анализ с помощью LLM
        # analysis = self.model.analyze(extracted_text)
        
        # Пока возвращаем заглушку
        return {
            "summary": "Краткое содержание документа (TODO: добавить реальный анализ)",
            "key_points": [
                "Ключевой пункт 1",
                "Ключевой пункт 2",
                "Ключевой пункт 3"
            ],
            "entities": {
                "dates": ["01.01.2024"],
                "names": ["Иван Иванов"],
                "organizations": ["ООО Компания"]
            },
            "document_type": "Договор/Отчет/Заявление (определить автоматически)",
            "extracted_text_preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
        }
    
    def _extract_text(self, file_path, file_type):
        """
        Извлекает текст из файла.
        
        TODO: Реализовать для разных типов файлов:
        - PDF: import PyPDF2 или pdfplumber
        - DOCX: import docx
        - Images: import pytesseract
        - TXT: просто читать файл
        """
        if file_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Для остальных типов - заглушка
        return f"Текст из файла {file_type} (TODO: реализовать извлечение)"
    
    def chat_with_document(self, user_message, document_context, chat_history):
        """
        Отвечает на вопросы пользователя о документе.
        
        Args:
            user_message: сообщение пользователя
            document_context: контекст документа (результат анализа)
            chat_history: история чата для контекста
        
        Returns:
            dict: ответ с thinking steps и текстом ответа
        """
        # TODO: Реализовать генерацию ответа с помощью LLM
        # Использовать RAG (Retrieval-Augmented Generation) если нужно
        
        # Симуляция thinking process
        thinking_steps = [
            "Анализирую ваш вопрос...",
            "Ищу релевантную информацию в документе...",
            "Формулирую ответ на основе контекста..."
        ]
        
        # TODO: Настоящий ответ от модели
        # response = self.model.generate(
        #     prompt=user_message,
        #     context=document_context,
        #     history=chat_history
        # )
        
        response = f"Ответ на '{user_message}' на основе документа (TODO: добавить реальный LLM)"
        
        return {
            "thinking_steps": thinking_steps,
            "response": response
        }


# Инициализируем анализатор
analyzer = DocumentAnalyzer()

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({"status": "ok", "message": "Backend is running"})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Загрузка и первичный анализ документа.
    
    Ожидает: multipart/form-data с файлом
    Возвращает: результат анализа документа
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {ALLOWED_EXTENSIONS}"}), 400
    
    try:
        # Сохраняем файл
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Определяем тип файла
        file_type = filename.rsplit('.', 1)[1].lower()
        
        # Анализируем документ
        analysis_result = analyzer.analyze_document(file_path, file_type)
        
        return jsonify({
            "success": True,
            "filename": filename,
            "file_id": unique_filename,
            "analysis": analysis_result
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Обработка сообщений в чате с документом.
    
    Ожидает JSON:
    {
        "message": "текст сообщения",
        "file_id": "id загруженного файла (optional)",
        "document_context": {...}, // результат анализа документа
        "chat_history": [...] // предыдущие сообщения
    }
    
    Возвращает:
    {
        "thinking_steps": [...],
        "response": "ответ модели"
    }
    """
    data = request.json
    
    if not data or 'message' not in data:
        return jsonify({"error": "No message provided"}), 400
    
    user_message = data['message']
    document_context = data.get('document_context', {})
    chat_history = data.get('chat_history', [])
    
    try:
        # Имитируем задержку обработки
        time.sleep(1)
        
        # Получаем ответ от модели
        result = analyzer.chat_with_document(
            user_message=user_message,
            document_context=document_context,
            chat_history=chat_history
        )
        
        return jsonify({
            "success": True,
            **result
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/reanalyze', methods=['POST'])
def reanalyze():
    """
    Повторный анализ документа с дополнительными параметрами.
    
    Ожидает JSON:
    {
        "file_id": "id файла",
        "focus": "на чём сфокусироваться (optional)"
    }
    """
    data = request.json
    
    if not data or 'file_id' not in data:
        return jsonify({"error": "No file_id provided"}), 400
    
    file_id = data['file_id']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        file_type = file_id.rsplit('.', 1)[1].lower()
        analysis_result = analyzer.analyze_document(file_path, file_type)
        
        return jsonify({
            "success": True,
            "analysis": analysis_result
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Flask Backend запущен!")
    print("=" * 50)
    print("\n📋 TODO для вашего друга:")
    print("1. Установить зависимости: pip install flask flask-cors PyPDF2 python-docx pytesseract")
    print("2. Реализовать DocumentAnalyzer._extract_text() для разных типов файлов")
    print("3. Интегрировать LLM модель в DocumentAnalyzer.__init__()")
    print("4. Реализовать analyze_document() с реальным анализом")
    print("5. Реализовать chat_with_document() с генерацией ответов")
    print("\n🔗 API Endpoints:")
    print("GET  /api/health - проверка работоспособности")
    print("POST /api/upload - загрузка и анализ документа")
    print("POST /api/chat - общение с ботом о документе")
    print("POST /api/reanalyze - повторный анализ")
    print("=" * 50)
    print()
    
    app.run(debug=True, port=5000)