import {
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createKit, listKits } from '../api/admin'
import { formatRange } from './format'

// Список китов с быстрым созданием черновика.
export function KitsListPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)
  const [name, setName] = useState('')

  const { data: kits, isLoading } = useQuery({ queryKey: ['kits'], queryFn: listKits })

  const createMutation = useMutation({
    mutationFn: () => createKit({ name }),
    onSuccess: async (kit) => {
      await queryClient.invalidateQueries({ queryKey: ['kits'] })
      close()
      setName('')
      navigate(`/admin/kits/${kit.id}`)
    },
  })

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Киты</Title>
        <Button onClick={open}>Создать кит</Button>
      </Group>

      {isLoading && <Loader />}

      {kits && kits.length === 0 && <Text c="dimmed">Пока нет ни одного кита.</Text>}

      {kits && kits.length > 0 && (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Название</Table.Th>
              <Table.Th>Роль</Table.Th>
              <Table.Th>Статус</Table.Th>
              <Table.Th>Цена</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {kits.map((kit) => (
              <Table.Tr
                key={kit.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/admin/kits/${kit.id}`)}
              >
                <Table.Td>{kit.name}</Table.Td>
                <Table.Td>{kit.role ?? '—'}</Table.Td>
                <Table.Td>
                  <Badge color={kit.status === 'published' ? 'green' : 'gray'}>
                    {kit.status === 'published' ? 'опубликован' : 'черновик'}
                  </Badge>
                </Table.Td>
                <Table.Td>{formatRange(kit.pricing)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="Новый кит">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            createMutation.mutate()
          }}
        >
          <Stack>
            <TextInput
              label="Название"
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
              autoFocus
            />
            <Button type="submit" loading={createMutation.isPending} disabled={!name}>
              Создать
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
