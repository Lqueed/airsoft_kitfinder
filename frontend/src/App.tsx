import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AdminLayout } from './admin/AdminLayout'
import { KitEditorPage } from './admin/KitEditorPage'
import { KitsListPage } from './admin/KitsListPage'
import { LoginPage } from './admin/LoginPage'
import { OffersPage } from './admin/OffersPage'
import { ProductsPage } from './admin/ProductsPage'
import { CatalogPage } from './pages/CatalogPage'
import { KitDetailPage } from './pages/KitDetailPage'
import { SearchPage } from './pages/SearchPage'
import { WizardPage } from './pages/WizardPage'

const queryClient = new QueryClient()

function App() {
  return (
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<CatalogPage />} />
            <Route path="/wizard" element={<WizardPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/kits/:slug" element={<KitDetailPage />} />
            <Route path="/admin/login" element={<LoginPage />} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<KitsListPage />} />
              <Route path="kits/:id" element={<KitEditorPage />} />
              <Route path="products" element={<ProductsPage />} />
              <Route path="offers" element={<OffersPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </MantineProvider>
  )
}

export default App
