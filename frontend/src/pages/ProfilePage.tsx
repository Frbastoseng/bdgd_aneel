import { useAuthStore } from '@/stores/authStore'
import { UserIcon } from '@heroicons/react/24/outline'

export default function ProfilePage() {
  const { user } = useAuthStore()
  
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Meu Perfil</h1>
        <p className="text-gray-600">
          Visualize e gerencie suas informações de conta
        </p>
      </div>
      
      <div className="card">
        <div className="card-header flex items-center gap-4">
          <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
            <UserIcon className="w-8 h-8 text-primary-600" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {user?.full_name}
            </h2>
            <p className="text-gray-600">{user?.email}</p>
          </div>
        </div>
        
        <div className="card-body space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Empresa</label>
              <p className="text-gray-900">{user?.company || '-'}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Telefone</label>
              <p className="text-gray-900">{user?.phone || '-'}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Função</label>
              <p className="text-gray-900 capitalize">{user?.role}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Status</label>
              <p className="text-gray-900 capitalize">{user?.status}</p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Membro desde</label>
              <p className="text-gray-900">
                {user?.created_at && new Date(user.created_at).toLocaleDateString('pt-BR')}
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Último acesso</label>
              <p className="text-gray-900">
                {user?.last_login 
                  ? new Date(user.last_login).toLocaleString('pt-BR')
                  : '-'
                }
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
