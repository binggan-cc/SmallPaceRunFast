export interface User {
  id: string;
  name: string;
}

export type UserRole = "admin" | "user";

export class UserModel {
  constructor(public user: User) {}
}
