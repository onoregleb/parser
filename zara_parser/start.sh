#!/bin/bash

# Скрипт для запуска Zara API парсера на AWS сервере
# Использование: ./start.sh [test|full|resume|stop|status|logs|monitor|cleanup|help]

set -e

PROJECT_NAME="zara-api-parser"
COMPOSE_FILE="docker-compose.yml"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ ERROR: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] ℹ️  INFO: $1${NC}"
}

header() {
    echo -e "${PURPLE}"
    echo "=================================================================="
    echo "  🕷️  ZARA API PARSER - AWS DEPLOYMENT SCRIPT"
    echo "=================================================================="
    echo -e "${NC}"
}

# Функция проверки зависимостей
check_dependencies() {
    log "Проверка зависимостей..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker не установлен!"
        echo "Установите Docker: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        error "Docker Compose не установлен!"
        echo "Установите Docker Compose или используйте 'docker compose' вместо 'docker-compose'"
        exit 1
    fi
    
    # Проверяем какая команда доступна
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    log "Все зависимости установлены (используется: $DOCKER_COMPOSE)"
}

# Функция подготовки окружения
prepare_environment() {
    log "Подготовка окружения..."
    
    # Создаем необходимые директории
    mkdir -p output logs
    
    # Устанавливаем права доступа
    chmod +x start.sh
    
    # Проверяем наличие файла api_en.py
    if [ ! -f "api_en.py" ]; then
        error "Файл api_en.py не найден в текущей директории!"
        exit 1
    fi
    
    log "Окружение подготовлено"
}

# Функция запуска парсера
start_parser() {
    local mode=$1
    
    log "Запуск парсера в режиме: $mode"
    
    case $mode in
        "test")
            log "Запуск в тестовом режиме (первые 3 категории для взрослых)..."
            $DOCKER_COMPOSE -p $PROJECT_NAME up -d --build
            sleep 5
            $DOCKER_COMPOSE -p $PROJECT_NAME exec zara-api-parser python -u api_en.py --test --adults
            ;;
        "full")
            log "Запуск полного парсинга (все категории для взрослых)..."
            $DOCKER_COMPOSE -p $PROJECT_NAME up -d --build
            ;;
        "resume")
            log "Возобновление парсинга с сохраненного прогресса..."
            $DOCKER_COMPOSE -p $PROJECT_NAME up -d --build
            sleep 5
            $DOCKER_COMPOSE -p $PROJECT_NAME exec zara-api-parser python -u api_en.py --adults --resume
            ;;
        *)
            error "Неизвестный режим: $mode"
            show_usage
            exit 1
            ;;
    esac
    
    log "Парсер запущен в фоновом режиме!"
    info "Используйте './start.sh status' для проверки статуса"
    info "Используйте './start.sh logs' для просмотра логов"
}

# Функция остановки парсера
stop_parser() {
    log "Остановка парсера..."
    $DOCKER_COMPOSE -p $PROJECT_NAME down
    log "Парсер остановлен"
}

# Функция проверки статуса
check_status() {
    log "Проверка статуса парсера..."
    echo ""
    
    # Показать статус контейнеров
    info "Статус контейнеров:"
    $DOCKER_COMPOSE -p $PROJECT_NAME ps
    
    # Показать использование ресурсов если контейнеры запущены
    if $DOCKER_COMPOSE -p $PROJECT_NAME ps -q | grep -q .; then
        echo ""
        info "Использование ресурсов:"
        docker stats --no-stream $($DOCKER_COMPOSE -p $PROJECT_NAME ps -q) 2>/dev/null || true
        
        echo ""
        info "Последние строки из логов:"
        $DOCKER_COMPOSE -p $PROJECT_NAME logs --tail=10 zara-api-parser
    else
        warn "Контейнеры не запущены"
    fi
}

# Функция просмотра логов
show_logs() {
    local service=${1:-"zara-api-parser"}
    local lines=${2:-100}
    
    log "Показ последних $lines строк логов сервиса: $service"
    echo ""
    
    if $DOCKER_COMPOSE -p $PROJECT_NAME ps -q $service | grep -q .; then
        $DOCKER_COMPOSE -p $PROJECT_NAME logs -f --tail=$lines $service
    else
        error "Сервис $service не запущен"
        info "Запустите парсер командой: ./start.sh full"
    fi
}

# Функция запуска мониторинга
start_monitoring() {
    log "Запуск веб-мониторинга логов..."
    $DOCKER_COMPOSE -p $PROJECT_NAME --profile monitoring up -d log-viewer
    echo ""
    info "🌐 Веб-мониторинг доступен по адресу: http://localhost:8080"
    info "📝 Или http://YOUR_AWS_IP:8080 (замените YOUR_AWS_IP на IP вашего сервера)"
    echo ""
    warn "Убедитесь что порт 8080 открыт в security group AWS!"
}

# Функция очистки
cleanup() {
    warn "Очистка старых контейнеров и образов..."
    
    # Останавливаем наши контейнеры
    $DOCKER_COMPOSE -p $PROJECT_NAME down 2>/dev/null || true
    
    # Очищаем неиспользуемые ресурсы Docker
    docker system prune -f
    docker volume prune -f
    
    log "Очистка завершена"
}

# Функция показа информации о файлах
show_files() {
    log "Информация о созданных файлах:"
    echo ""
    
    if [ -d "output" ]; then
        info "📁 Директория output/ (JSON файлы):"
        ls -la output/ 2>/dev/null || echo "  Пусто"
    fi
    
    if [ -d "logs" ]; then
        info "📁 Директория logs/ (логи парсера):"
        ls -la logs/ 2>/dev/null || echo "  Пусто"  
    fi
    
    info "📄 JSON файлы в текущей директории:"
    ls -la *.json 2>/dev/null || echo "  Нет JSON файлов"
}

# Функция показа использования
show_usage() {
    header
    echo "Использование: $0 [COMMAND]"
    echo ""
    echo "📋 ДОСТУПНЫЕ КОМАНДЫ:"
    echo ""
    echo "  🧪 test      - Запуск в тестовом режиме (3 категории)"
    echo "  🚀 full      - Запуск полного парсинга (все взрослые категории)" 
    echo "  ⏯️  resume    - Возобновить парсинг с последнего сохранения"
    echo "  ⏹️  stop      - Остановить парсер"
    echo "  📊 status    - Показать статус парсера и ресурсов"
    echo "  📝 logs      - Показать логи парсера"
    echo "  🌐 monitor   - Запустить веб-мониторинг логов (порт 8080)"
    echo "  📁 files     - Показать созданные файлы"
    echo "  🗑️  cleanup   - Очистить неиспользуемые Docker ресурсы"
    echo "  ❓ help      - Показать эту справку"
    echo ""
    echo "💡 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:"
    echo ""
    echo "  ./start.sh test          # Тестовый запуск (быстро)"
    echo "  ./start.sh full          # Полный парсинг всех категорий"
    echo "  ./start.sh status        # Проверить что происходит"
    echo "  ./start.sh logs          # Посмотреть логи в реальном времени"
    echo "  ./start.sh monitor       # Открыть веб-интерфейс для логов"
    echo "  ./start.sh files         # Посмотреть какие файлы созданы"
    echo ""
    echo "🔧 ПОЛЕЗНАЯ ИНФОРМАЦИЯ:"
    echo ""
    echo "  • Парсер сохраняет данные в JSON файлы в текущей директории"
    echo "  • Логи сохраняются в папку logs/"
    echo "  • Веб-мониторинг доступен на порту 8080"
    echo "  • Парсер автоматически перезапускается при падении"
    echo "  • Можно безопасно закрыть терминал - парсер будет работать в фоне"
    echo ""
}

# Основная логика
main() {
    local command=${1:-"help"}
    
    case $command in
        "test"|"full"|"resume")
            header
            check_dependencies
            prepare_environment
            start_parser $command
            echo ""
            info "🎉 Парсер успешно запущен!"
            info "📋 Полезные команды:"
            echo "     ./start.sh status   - проверить статус"
            echo "     ./start.sh logs     - смотреть логи"
            echo "     ./start.sh files    - посмотреть файлы"
            echo "     ./start.sh stop     - остановить"
            ;;
        "stop")
            stop_parser
            ;;
        "status")
            check_status
            ;;
        "logs")
            show_logs ${2:-"zara-api-parser"} ${3:-100}
            ;;
        "monitor")
            start_monitoring
            ;;
        "files")
            show_files
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|*)
            show_usage
            ;;
    esac
}

# Перехват сигналов для корректного завершения
trap 'echo ""; warn "Получен сигнал завершения..."; exit 0' INT TERM

# Запуск основной функции
main "$@"
