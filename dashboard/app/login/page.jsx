"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "../../lib/api";

export default function Login() {
  const router = useRouter();
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");

  async function doLogin() {
    try {
      const data = await login(user, pass);

      if (data.access_token) {
        router.push("/");
      } else {
        alert("Login failed");
      }
    } catch (err) {
      alert("Unable to reach the login service.");
    }
  }

  return (
    <div style={{ background: "black", height: "100vh", display: "flex", justifyContent: "center", alignItems: "center"}}>
      <div style={{ background: "#111", padding: "40px", borderRadius: "10px", width: "320px", border: "1px solid gold" }}>
        <h2 style={{ color: "gold", marginBottom: "20px" }}>Admin Login</h2>

        <input value={user} onChange={(e)=>setUser(e.target.value)} placeholder="Username"
          style={{ width:"100%", padding:"10px", marginBottom:"10px", background:"#222", border:"1px solid #333", color:"white" }}
        />

        <input type="password" value={pass} onChange={(e)=>setPass(e.target.value)} placeholder="Password"
          style={{ width:"100%", padding:"10px", background:"#222", border:"1px solid #333", color:"white" }}
        />

        <button onClick={doLogin}
          style={{ marginTop:"15px", width:"100%", padding:"10px", background:"gold", border:"none", color:"black", fontWeight:"bold" }}>
          Login
        </button>
      </div>
    </div>
  );
}
