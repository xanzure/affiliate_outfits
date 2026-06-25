import { redirect } from "next/navigation"
import { getAdminUser } from "@/lib/auth"
import { getConceptOptions } from "@/lib/admin"
import AdminNav from "@/components/admin/AdminNav"
import GlobalActions from "@/components/admin/GlobalActions"
import { signOut } from "./actions"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getAdminUser()
  if (!user) redirect("/admin/login")
  const concepts = await getConceptOptions()

  return (
    <div className="flex h-screen overflow-hidden">
      <AdminNav
        actions={
          <>
            <GlobalActions concepts={concepts} />
            <form action={signOut}>
              <button className="w-full rounded-sm px-3 py-2 text-left text-[0.7rem] tracking-[0.2em] uppercase text-muted transition-colors hover:text-accent">
                Log out
              </button>
            </form>
          </>
        }
      />
      <main className="flex-1 overflow-y-auto px-5 pb-24 pt-16 sm:px-8 md:pb-10 md:pt-10">
        <div className="mx-auto max-w-[1100px]">{children}</div>
      </main>
    </div>
  )
}
