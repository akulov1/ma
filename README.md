# Итоговая работа: Microservices + Kubernetes + Helm (user-platform-exam)

Этот репозиторий закрывает требования на **«отлично»**:
- Namespace: `user-platform-exam`
- 4 микросервиса: auth, profile, notification, report + ui (NodePort)
- Postgres (1 Pod) + сервис ClusterIP
- Probes: `/health/live` и `/health/ready` (initialDelaySeconds=30, periodSeconds=10)
- Secrets: DB_PASSWORD, JWT_SECRET
- ConfigMap: app-config (нефункциональные параметры), ui-config (тексты интерфейса)
- 3 CronJob: daily-stats-collector, notification-sender (Forbid), data-cleanup
- Helm Chart: `helm/user-platform-exam`

## 1) «Удовлетворительно» (монолит)
Файлы в `k8s-plain/`:
- 2 реплики monolith-app + NodePort
- 1 реплика postgres + ClusterIP
- ConfigMap + Secret
Применение:
```bash
kubectl apply -f k8s-plain/
```
ВАЖНО: замените образ `your-registry/monolith-app:1.0.0` на ваш.

## 2) «Отлично» (Helm, микросервисы)
### Сборка образов
Каждый сервис имеет свой Dockerfile:
- `services/auth-service`
- `services/profile-service`
- `services/notification-service`
- `services/report-service`
- `services/ui-service`

Пример:
```bash
docker build -t your-registry/auth-service:1.0.0 services/auth-service
docker build -t your-registry/profile-service:1.0.0 services/profile-service
docker build -t your-registry/notification-service:1.0.0 services/notification-service
docker build -t your-registry/report-service:1.0.0 services/report-service
docker build -t your-registry/ui-service:1.0.0 services/ui-service
docker push your-registry/auth-service:1.0.0
# ... остальные push
```

### Установка Helm
В `helm/user-platform-exam/values.yaml` укажите ваши образы (`services.*.image`).

Установка:
```bash
helm upgrade --install user-platform helm/user-platform-exam --create-namespace --namespace user-platform-exam
```

Проверка:
```bash
kubectl -n user-platform-exam get all
kubectl -n user-platform-exam get cronjob
```

Доступ к UI (NodePort по умолчанию 30080):
- `http://<node-ip>:30080/`

## 3) Проверка критериев
- Labels присутствуют на Namespace/ConfigMap/Secret/Deployments/Services/CronJobs.
- Для каждого Deployment настроены liveness/readiness probes.
- У каждого сервиса минимум 2 реплики (в values.yaml).
- DB развернута отдельным Deployment с replicas: 1.

Удачи на защите!

## Страницы UI
- `/` — главная (описание + ссылки)
- `/register` — регистрация
- `/login` — авторизация
- `/me` — личная страница пользователя (профиль)

