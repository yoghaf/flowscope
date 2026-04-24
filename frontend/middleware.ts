import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Define public paths that don't require authentication
  const publicPaths = ['/', '/scanner', '/whale-radar', '/login'];
  
  // Get the current path
  const path = request.nextUrl.pathname;
  
  // Check if it's an API route or static file (allow these)
  if (path.startsWith('/api') || path.startsWith('/_next') || path.includes('.')) {
    return NextResponse.next();
  }

  // Check if the path is public
  const isPublicPath = publicPaths.includes(path) || publicPaths.some(p => p !== '/' && path.startsWith(p));
  
  // Special exception: root path '/' is exactly matched above, we also need to allow it
  if (path === '/') {
    return NextResponse.next();
  }

  if (isPublicPath) {
    return NextResponse.next();
  }

  // If it's a protected path, check for the auth cookie
  const authCookie = request.cookies.get('admin_auth');
  
  if (!authCookie || authCookie.value !== 'authenticated') {
    // Redirect to login page if not authenticated
    const loginUrl = new URL('/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

// See "Matching Paths" below to learn more
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};
