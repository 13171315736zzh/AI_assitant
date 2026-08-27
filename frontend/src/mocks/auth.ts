import type { ApiResponse, LoginData, User } from '@/types'

export const mockUsers: Record<string, { password: string; user: User }> = {
  admin: {
    password: 'admin123',
    user: {
      id: 1,
      username: 'admin',
      display_name: '管理员',
      role: 'admin',
      employee_id: '0000001',
    },
  },
  user_a: {
    password: 'usera123',
    user: {
      id: 2,
      username: 'user_a',
      display_name: '张明',
      role: 'employee',
      employee_id: '0176338',
    },
  },
  user_b: {
    password: 'userb123',
    user: {
      id: 3,
      username: 'user_b',
      display_name: '李华',
      role: 'employee',
      employee_id: '0176401',
    },
  },
}

export function mockLogin(username: string, password: string): ApiResponse<LoginData> {
  const account = mockUsers[username]
  if (!account || account.password !== password) {
    return { code: 401, message: '用户名或密码错误', data: null as unknown as LoginData }
  }
  return {
    code: 200,
    message: 'success',
    data: {
      access_token: `mock-token-${username}`,
      token_type: 'bearer',
      user: account.user,
    },
  }
}

export function mockLogout(): ApiResponse<null> {
  return { code: 200, message: 'success', data: null }
}

export function mockMe(userId: number): ApiResponse<User> {
  const user = Object.values(mockUsers).find((item) => item.user.id === userId)?.user
  if (!user) {
    return { code: 401, message: '未认证或 Token 已过期', data: null as unknown as User }
  }
  return { code: 200, message: 'success', data: user }
}
