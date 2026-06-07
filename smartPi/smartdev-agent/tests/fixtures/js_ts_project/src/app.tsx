import React from "react";
import { UserService } from "./services/user-service";

export default function App() {
  const service = new UserService();
  return <div>{service.createUser("1", "Alice").name}</div>;
}
