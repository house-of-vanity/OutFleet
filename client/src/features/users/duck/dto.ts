export interface User {}

export interface UserDTO {
  page: number
  per_page: number
  total: number
  users: User[]
}
