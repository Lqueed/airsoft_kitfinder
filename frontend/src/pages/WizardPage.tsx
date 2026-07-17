import {
  Anchor,
  Button,
  Container,
  Group,
  NumberInput,
  Select,
  Stepper,
  Text,
  Title,
} from '@mantine/core'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { getMeta } from '../api/admin'
import { recommend } from '../api/public'
import { KitCardGrid } from './KitCardGrid'

// Визард подбора кита: 3 шага (уровень, роль, бюджет) → рекомендации.
export function WizardPage() {
  const [active, setActive] = useState(0)
  const [experience, setExperience] = useState<string | null>(null)
  const [role, setRole] = useState<string | null>(null)
  const [budget, setBudget] = useState<number | string>('')

  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })

  const mutation = useMutation({
    mutationFn: () =>
      recommend({
        experience,
        role,
        budget: budget === '' ? null : Number(budget),
      }),
  })

  const submit = () => {
    setActive(3)
    mutation.mutate()
  }

  return (
    <Container py="xl" size="lg">
      <Anchor component={Link} to="/" size="sm">
        ← В каталог
      </Anchor>
      <Title order={1} mt="sm" mb="lg">
        Подбор кита
      </Title>

      <Stepper active={active} onStepClick={setActive}>
        <Stepper.Step label="Уровень" description="Ваш опыт">
          <Select
            mt="md"
            label="Уровень опыта"
            placeholder="Не важно"
            clearable
            data={meta?.experience_levels ?? []}
            value={experience}
            onChange={setExperience}
            w={280}
          />
        </Stepper.Step>

        <Stepper.Step label="Роль" description="Стиль игры">
          <Select
            mt="md"
            label="Роль"
            placeholder="Не важно"
            clearable
            data={meta?.roles ?? []}
            value={role}
            onChange={setRole}
            w={280}
          />
        </Stepper.Step>

        <Stepper.Step label="Бюджет" description="Сколько готовы потратить">
          <NumberInput
            mt="md"
            label="Бюджет, ₽"
            placeholder="Не важно"
            min={0}
            allowNegative={false}
            value={budget}
            onChange={setBudget}
            w={280}
          />
        </Stepper.Step>

        <Stepper.Completed>
          {mutation.isPending && <Text mt="md">Подбираем…</Text>}
          {mutation.isSuccess && mutation.data.length === 0 && (
            <Text mt="md" c="dimmed">
              Подходящих китов не нашлось.
            </Text>
          )}
          {mutation.isSuccess && mutation.data.length > 0 && (
            <>
              <Text mt="md" mb="sm" c="dimmed">
                Рекомендации (сверху — наиболее подходящие):
              </Text>
              <KitCardGrid kits={mutation.data} />
            </>
          )}
        </Stepper.Completed>
      </Stepper>

      <Group mt="xl">
        {active > 0 && active < 3 && (
          <Button variant="default" onClick={() => setActive((s) => s - 1)}>
            Назад
          </Button>
        )}
        {active < 2 && <Button onClick={() => setActive((s) => s + 1)}>Далее</Button>}
        {active === 2 && <Button onClick={submit}>Показать рекомендации</Button>}
        {active === 3 && (
          <Button variant="light" onClick={() => setActive(0)}>
            Начать заново
          </Button>
        )}
      </Group>
    </Container>
  )
}
