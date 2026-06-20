import { NextRequest, NextResponse } from "next/server"
import { createServerClient } from "@supabase/ssr"

export async function POST(request: NextRequest) {
  const formData = await request.formData()
  const email = formData.get("email") as string
  const password = formData.get("password") as string
  const base = request.nextUrl.origin

  // Build the success response first so we can attach cookies to it directly
  const successResponse = NextResponse.redirect(`${base}/admin/schedule`, { status: 303 })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) =>
            successResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const { error } = await supabase.auth.signInWithPassword({ email, password })

  if (error) {
    return NextResponse.redirect(
      `${base}/admin/login?error=${encodeURIComponent(error.message)}`,
      { status: 303 }
    )
  }

  return successResponse
}
