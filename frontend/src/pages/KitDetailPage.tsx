import {
  Anchor,
  Badge,
  Box,
  Button,
  Container,
  Group,
  Loader,
  Paper,
  Radio,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getKitDetail } from '../api/public'
import type { KitDetailItem, OfferView, VariantView } from '../api/types'
import { formatMinMax, formatPrice } from '../admin/format'

// Список магазинов с ценой и ссылкой «Купить».
function OfferList({ offers }: { offers: OfferView[] }) {
  if (offers.length === 0) return <Text size="sm" c="dimmed">Нет активных предложений.</Text>
  return (
    <Stack gap={4}>
      {offers.map((o) => (
        <Group key={`${o.shop.id}-${o.url}`} gap="sm">
          <Text size="sm" w={160}>
            {o.shop.name}
          </Text>
          <Text size="sm" fw={600} w={90}>
            {formatPrice(o.price)}
          </Text>
          <Anchor href={o.url} target="_blank" rel="noopener nofollow" size="sm">
            Купить →
          </Anchor>
        </Group>
      ))}
    </Stack>
  )
}

export function KitDetailPage() {
  const { slug } = useParams()
  const { data: kit, isLoading, isError } = useQuery({
    queryKey: ['kit-detail', slug],
    queryFn: () => getKitDetail(slug as string),
    enabled: !!slug,
  })

  // Выбор варианта для каждой flexible-позиции (по умолчанию — самый дешёвый).
  const [selection, setSelection] = useState<Record<number, string>>({})

  const getVariant = (item: KitDetailItem): VariantView | undefined => {
    if (item.variants.length === 0) return undefined
    const chosen = selection[item.id]
    return item.variants.find((v) => String(v.product.id) === chosen) ?? item.variants[0]
  }

  // Текущий итог: сумма выбранных цен по обязательным позициям.
  const currentTotal = useMemo(() => {
    if (!kit) return null
    let total = 0
    for (const item of kit.items) {
      if (!item.is_required) continue
      if (item.item_type === 'fixed') {
        if (item.min_price == null) return null
        total += Number(item.min_price)
      } else {
        const v = getVariant(item)
        if (!v || v.min_price == null) return null
        total += Number(v.min_price)
      }
    }
    return total
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kit, selection])

  if (isLoading) return <Loader m="xl" />
  if (isError || !kit) {
    return (
      <Container py="xl">
        <Text c="red">Кит не найден.</Text>
        <Anchor component={Link} to="/">
          ← В каталог
        </Anchor>
      </Container>
    )
  }

  return (
    <Container py="xl" size="md" pb={100}>
      <Anchor component={Link} to="/" size="sm">
        ← В каталог
      </Anchor>
      <Title order={1} mt="sm">
        {kit.name}
      </Title>
      <Group gap="xs" mt="xs">
        {kit.role && <Badge variant="light">{kit.role}</Badge>}
        {kit.drive_type && <Badge variant="light" color="grape">{kit.drive_type}</Badge>}
        {kit.experience_level && <Badge variant="light" color="teal">{kit.experience_level}</Badge>}
      </Group>
      {kit.description && (
        <Text mt="md" c="dimmed">
          {kit.description}
        </Text>
      )}

      <Title order={3} mt="xl" mb="sm">
        Состав
      </Title>
      <Stack>
        {kit.items.map((item) => (
          <Paper key={item.id} withBorder p="md">
            <Group justify="space-between" mb="xs">
              <Text fw={600}>
                {item.title}
                {!item.is_required && (
                  <Badge ml="xs" size="sm" color="gray" variant="light">
                    опционально
                  </Badge>
                )}
              </Text>
              <Text c="dimmed" size="sm">
                {item.item_type === 'fixed' ? 'конкретный товар' : 'на выбор'}
              </Text>
            </Group>

            {item.item_type === 'fixed' ? (
              <Stack gap="xs">
                {item.product && <Text size="sm">{item.product.name}</Text>}
                <OfferList offers={item.offers} />
              </Stack>
            ) : item.variants.length === 0 ? (
              <Text size="sm" c="dimmed">Нет доступных вариантов.</Text>
            ) : (
              <Radio.Group
                value={selection[item.id] ?? String(item.variants[0].product.id)}
                onChange={(v) => setSelection((s) => ({ ...s, [item.id]: v }))}
              >
                <Stack gap="sm">
                  {item.variants.map((v) => (
                    <Box key={v.product.id}>
                      <Radio
                        value={String(v.product.id)}
                        label={
                          <Group gap="xs">
                            <Text size="sm">{v.product.name}</Text>
                            <Text size="sm" fw={600} c="dimmed">
                              от {formatPrice(v.min_price)}
                            </Text>
                          </Group>
                        }
                      />
                      {(selection[item.id] ?? String(item.variants[0].product.id)) ===
                        String(v.product.id) && (
                        <Box pl="xl" pt={4}>
                          <OfferList offers={v.offers} />
                        </Box>
                      )}
                    </Box>
                  ))}
                </Stack>
              </Radio.Group>
            )}
          </Paper>
        ))}
      </Stack>

      {/* Липкая панель «Итого» */}
      <Paper
        withBorder
        p="md"
        style={{ position: 'sticky', bottom: 0, marginTop: 24 }}
        shadow="md"
      >
        <Group justify="space-between">
          <div>
            <Text size="xs" c="dimmed">
              Вилка кита: {formatMinMax(kit.price_min, kit.price_max, kit.complete)}
            </Text>
            <Title order={3}>
              Итого: {currentTotal == null ? '—' : formatPrice(currentTotal)}
            </Title>
          </div>
          <Button
            component={Link}
            to="/"
            variant="light"
          >
            К другим китам
          </Button>
        </Group>
      </Paper>
    </Container>
  )
}
