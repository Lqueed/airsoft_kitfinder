import { Alert, Button, Center, Paper, PasswordInput, Stack, Title } from '@mantine/core'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { login } from '../api/admin'
import { ApiError } from '../api/client'

// Страница логина админа: один пароль → cookie-сессия.
export function LoginPage() {
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => login(password),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['me'] })
      navigate('/admin')
    },
  })

  const wrongPassword = mutation.error instanceof ApiError && mutation.error.status === 401

  return (
    <Center h="100vh">
      <Paper withBorder shadow="sm" p="xl" w={360}>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            mutation.mutate()
          }}
        >
          <Stack>
            <Title order={3}>Вход в админку</Title>
            <PasswordInput
              label="Пароль"
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              autoFocus
            />
            {mutation.isError && (
              <Alert color="red">{wrongPassword ? 'Неверный пароль' : 'Ошибка входа'}</Alert>
            )}
            <Button type="submit" loading={mutation.isPending} disabled={!password}>
              Войти
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  )
}
