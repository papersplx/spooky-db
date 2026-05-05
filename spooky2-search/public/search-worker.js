/**
 * Spooky2 Search API - Cloudflare Worker
 * Uses Neon serverless driver to query Postgres from the edge
 */
import { neon } from '@neondatabase/serverless';

export default {
  async fetch(request, env, ctx) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const sql = neon(env.NEON_CONN_STRING);

    try {
      if (url.pathname === '/search') {
        const query = url.searchParams.get('q') || '';
        const modes = url.searchParams.getAll('mode');
        const collections = url.searchParams.getAll('collection');
        const limit = parseInt(url.searchParams.get('limit') || '100');

        let whereClauses = [];
        let params = [];
        let paramIdx = 1;

        if (query) {
          whereClauses.push(`to_tsvector('english', name || ' ' || COALESCE(description, '')) @@ plainto_tsquery('english', $${paramIdx})`);
          params.push(query);
          paramIdx++;
        }

        if (modes.length > 0) {
          whereClauses.push(`mode = ANY($${paramIdx})`);
          params.push(modes);
          paramIdx++;
        }

        if (collections.length > 0) {
          whereClauses.push(`collection = ANY($${paramIdx})`);
          params.push(collections);
          paramIdx++;
        }

        const where = whereClauses.length > 0 ? `WHERE ${whereClauses.join(' AND ')}` : '';

        const results = await sql`
          SELECT id, name, description, collection, mode, entry_type
          FROM programs
          ${where ? sql.unsafe(where, ...params) : sql.unsafe('')}
          ORDER BY name
          LIMIT ${limit}
        `;

        return new Response(JSON.stringify(results), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      if (url.pathname === '/program') {
        const id = url.searchParams.get('id');
        if (!id) {
          return new Response(JSON.stringify({ error: 'Missing id' }), {
            status: 400,
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }

        const results = await sql`
          SELECT *
          FROM programs
          WHERE id = ${id}
          LIMIT 1
        `;

        if (results.length === 0) {
          return new Response(JSON.stringify({ error: 'Not found' }), {
            status: 404,
            headers: corsHeaders,
          });
        }

        return new Response(JSON.stringify(results[0]), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      if (url.pathname === '/collections') {
        const results = await sql`
          SELECT collection, COUNT(*) as count
          FROM programs
          GROUP BY collection
          ORDER BY collection
        `;
        return new Response(JSON.stringify(results), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      return new Response(JSON.stringify({ error: 'Not found' }), {
        status: 404,
        headers: corsHeaders,
      });
    } catch (error) {
      return new Response(JSON.stringify({ error: error.message }), {
        status: 500,
        headers: corsHeaders,
      });
    }
  },
};
