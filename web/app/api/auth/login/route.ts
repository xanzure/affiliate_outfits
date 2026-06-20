import { NextRequest, NextResponse } from "next/server"
import { createSupabaseServerClient } from "@/lib/supabase/server"

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const email = formData.get("email") as string
  const password = formData.get("password") as string

  const supabase = await createSupabaseServerClient()
  const { error } = await supabase.auth.signInWithPassword({ email, password })

  const base = request.nextUrl.origin
  if (error) {
    return NextResponse.redirect(
      `${base}/admin/login?error=${encodeURIComponent(error.message)}`,
      { status: 303 }
    )
  }
  return NextResponse.redirect(`${base}/admin/schedule`, { status: 303 })
}
