export function usePermissions() {
  const { t, te } = useI18n()
  const permissionLabel = (permission: string) => te(`permissions.${permission}`) ? t(`permissions.${permission}`) : permission
  const permissionItems = (permissions: string[]) => permissions.map(value => ({ label: permissionLabel(value), value }))
  return { permissionLabel, permissionItems }
}
