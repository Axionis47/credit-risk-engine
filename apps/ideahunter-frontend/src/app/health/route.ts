import { NextResponse } from 'next/server'

export async function GET() {
  try {
    // Basic health checks
    const healthStatus = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      service: 'ideahunter-frontend',
      version: process.env.npm_package_version || '1.0.0',
      environment: process.env.NODE_ENV || 'development',
      checks: {
        api_url: process.env.NEXT_PUBLIC_API_URL ? 'configured' : 'missing',
        google_client_id: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ? 'configured' : 'missing'
      }
    }

    // Check if critical environment variables are present
    const criticalEnvVars = [
      'NEXT_PUBLIC_API_URL',
      'NEXT_PUBLIC_GOOGLE_CLIENT_ID'
    ]

    const missingEnvVars = criticalEnvVars.filter(envVar => !process.env[envVar])
    
    if (missingEnvVars.length > 0) {
      return NextResponse.json({
        ...healthStatus,
        status: 'unhealthy',
        error: `Missing environment variables: ${missingEnvVars.join(', ')}`
      }, { status: 503 })
    }

    return NextResponse.json(healthStatus, { status: 200 })
  } catch (error) {
    return NextResponse.json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      service: 'ideahunter-frontend',
      error: 'Health check failed'
    }, { status: 503 })
  }
}

export async function HEAD() {
  // Simple HEAD request for load balancer health checks
  return new Response(null, { status: 200 })
}
