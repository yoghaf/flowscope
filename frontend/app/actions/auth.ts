"use server";

import { cookies } from "next/headers";

export async function verifyPin(pin: string) {
  const correctPin = process.env.ADMIN_PIN || "000000";
  
  if (pin === correctPin) {
    // Set cookie that expires in 30 days
    cookies().set("admin_auth", "authenticated", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 30 * 24 * 60 * 60, // 30 days
      path: "/",
    });
    return { success: true };
  }
  
  return { success: false, error: "Invalid PIN code" };
}

export async function logout() {
  cookies().delete("admin_auth");
}
