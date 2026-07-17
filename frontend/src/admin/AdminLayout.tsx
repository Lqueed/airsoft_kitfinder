import { AppShell, Button, Group, Loader, NavLink, Text, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { getMe, logout } from '../api/admin'

// Обёртка админки: гард по /admin/me и навигация. 401 → редирект на логин.
export function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    retry: false,
  })

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.setQueryData(['me'], null)
      navigate('/admin/login')
    },
  })

  if (isLoading) return <Loader m="xl" />
  if (isError || !data?.admin) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
  }

  const links = [
    { to: '/admin', label: 'Киты' },
    { to: '/admin/offers', label: 'Каталог магазинов' },
  ]

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 240, breakpoint: 'sm' }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Title order={4}>kitfinder · админка</Title>
          <Button variant="subtle" onClick={() => logoutMutation.mutate()}>
            Выйти
          </Button>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {links.map((link) => (
          <NavLink
            key={link.to}
            label={link.label}
            active={location.pathname === link.to}
            onClick={() => navigate(link.to)}
          />
        ))}
        <Text size="xs" c="dimmed" mt="md" px="sm">
          MVP-админка китов
        </Text>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
