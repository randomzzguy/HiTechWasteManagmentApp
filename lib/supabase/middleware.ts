import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  // Supabase credentials not configured - pass through without auth
  // To enable Supabase auth, add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    // No Supabase credentials - allow request to proceed without authentication
    return NextResponse.next({
      request,
    });
  }

  // If credentials are configured in the future, implement Supabase session handling here
  return NextResponse.next({
    request,
  });
}
