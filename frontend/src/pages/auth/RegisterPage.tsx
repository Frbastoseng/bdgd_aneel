import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'

interface RegisterForm {
  email: string
  password: string
  confirmPassword: string
  full_name: string
  company?: string
  phone?: string
  message?: string
}

export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { register: registerUser, isLoading } = useAuthStore()
  const navigate = useNavigate()
  
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterForm>()
  
  const password = watch('password')
  
  const onSubmit = async (data: RegisterForm) => {
    try {
      await registerUser({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        company: data.company,
        phone: data.phone,
        message: data.message,
      })
      toast.success('Cadastro realizado! Aguarde a aprovação do administrador.')
      navigate('/pending-approval')
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      const message = err.response?.data?.detail || 'Erro ao registrar'
      toast.error(message)
    }
  }
  
  return (
    <div className="card p-8 animate-slide-in">
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-gray-900">⚡ BDGD Pro</h1>
        <p className="text-gray-600 mt-2">Crie sua conta</p>
      </div>
      
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="full_name" className="label">
            Nome Completo *
          </label>
          <input
            id="full_name"
            type="text"
            className={errors.full_name ? 'input-error' : 'input'}
            {...register('full_name', {
              required: 'Nome é obrigatório',
              minLength: {
                value: 3,
                message: 'Nome deve ter no mínimo 3 caracteres',
              },
            })}
          />
          {errors.full_name && (
            <p className="mt-1 text-sm text-red-600">{errors.full_name.message}</p>
          )}
        </div>
        
        <div>
          <label htmlFor="email" className="label">
            Email *
          </label>
          <input
            id="email"
            type="email"
            className={errors.email ? 'input-error' : 'input'}
            {...register('email', {
              required: 'Email é obrigatório',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Email inválido',
              },
            })}
          />
          {errors.email && (
            <p className="mt-1 text-sm text-red-600">{errors.email.message}</p>
          )}
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="company" className="label">
              Empresa
            </label>
            <input
              id="company"
              type="text"
              className="input"
              {...register('company')}
            />
          </div>
          
          <div>
            <label htmlFor="phone" className="label">
              Telefone
            </label>
            <input
              id="phone"
              type="tel"
              className="input"
              {...register('phone')}
            />
          </div>
        </div>
        
        <div>
          <label htmlFor="password" className="label">
            Senha *
          </label>
          <div className="relative">
            <input
              id="password"
              type={showPassword ? 'text' : 'password'}
              className={errors.password ? 'input-error pr-10' : 'input pr-10'}
              {...register('password', {
                required: 'Senha é obrigatória',
                minLength: {
                  value: 8,
                  message: 'Senha deve ter no mínimo 8 caracteres',
                },
              })}
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showPassword ? (
                <EyeSlashIcon className="w-5 h-5" />
              ) : (
                <EyeIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          {errors.password && (
            <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
          )}
        </div>
        
        <div>
          <label htmlFor="confirmPassword" className="label">
            Confirmar Senha *
          </label>
          <input
            id="confirmPassword"
            type="password"
            className={errors.confirmPassword ? 'input-error' : 'input'}
            {...register('confirmPassword', {
              required: 'Confirmação é obrigatória',
              validate: (value) =>
                value === password || 'As senhas não conferem',
            })}
          />
          {errors.confirmPassword && (
            <p className="mt-1 text-sm text-red-600">{errors.confirmPassword.message}</p>
          )}
        </div>
        
        <div>
          <label htmlFor="message" className="label">
            Mensagem para o Administrador
          </label>
          <textarea
            id="message"
            rows={3}
            placeholder="Explique brevemente por que deseja acesso ao sistema..."
            className="input resize-none"
            {...register('message')}
          />
        </div>
        
        <button
          type="submit"
          disabled={isLoading}
          className="w-full btn-primary py-3"
        >
          {isLoading ? (
            <span className="spinner" />
          ) : (
            'Criar Conta'
          )}
        </button>
      </form>
      
      <div className="mt-6 text-center">
        <p className="text-sm text-gray-600">
          Já tem uma conta?{' '}
          <Link to="/login" className="text-primary-600 hover:text-primary-700 font-medium">
            Faça login
          </Link>
        </p>
      </div>
    </div>
  )
}
