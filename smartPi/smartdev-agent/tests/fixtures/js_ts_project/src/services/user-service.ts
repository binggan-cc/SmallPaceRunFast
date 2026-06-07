import { User, UserModel } from "../models/user";
import { formatName } from "../utils/format";

export class UserService {
  createUser(id: string, name: string): User {
    return { id, name: formatName(name) };
  }
}
