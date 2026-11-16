export const permissionLabels: Record<string, string> = {
  'functions.read': 'Чтение функций и реализаций',
  'functions.create': 'Создание функций',
  'functions.update': 'Редактирование функций и реализаций',
  'functions.delete': 'Удаление и восстановление функций',
  'functions.publish': 'Публичный доступ к запуску',
  'functions.run': 'Запуск функций',
  'runs.read': 'Чтение своих запусков',
  'runs.read_all': 'Чтение всех запусков',
  'runs.cancel': 'Отмена своих запусков',
  'runs.cancel_all': 'Отмена чужих запусков',
  'users.manage': 'Управление пользователями',
  'roles.manage': 'Управление ролями',
  'keys.manage': 'Управление своими API-ключами'
}

export function permissionItems(permissions: string[]) {
  return permissions.map(value => ({ label: permissionLabels[value] || value, value }))
}
