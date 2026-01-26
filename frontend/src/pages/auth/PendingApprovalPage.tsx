import { Link } from 'react-router-dom'
import { ClockIcon, CheckCircleIcon } from '@heroicons/react/24/outline'

export default function PendingApprovalPage() {
  return (
    <div className="card p-8 text-center animate-slide-in">
      <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <ClockIcon className="w-8 h-8 text-yellow-600" />
      </div>
      
      <h1 className="text-2xl font-bold text-gray-900 mb-2">
        Aguardando Aprovação
      </h1>
      
      <p className="text-gray-600 mb-6">
        Sua conta foi criada com sucesso! O administrador irá revisar sua
        solicitação e você receberá uma notificação assim que for aprovada.
      </p>
      
      <div className="bg-gray-50 rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium text-gray-900 mb-3">Próximos passos:</h3>
        <ul className="space-y-2 text-sm text-gray-600 text-left">
          <li className="flex items-start gap-2">
            <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
            <span>Conta criada com sucesso</span>
          </li>
          <li className="flex items-start gap-2">
            <ClockIcon className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
            <span>Aguardando revisão do administrador</span>
          </li>
          <li className="flex items-start gap-2">
            <div className="w-5 h-5 border-2 border-gray-300 rounded-full flex-shrink-0 mt-0.5" />
            <span>Acesso liberado após aprovação</span>
          </li>
        </ul>
      </div>
      
      <Link to="/login" className="btn-outline">
        Voltar para Login
      </Link>
    </div>
  )
}
