#!/usr/bin/env python3
"""
ContextBridge MCP Server
Provides screen context data to OpenClaw via MCP protocol
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
import threading
import time

class ContextDatabase:
    def __init__(self, db_path: str = "context_history.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize SQLite database for context storage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS context_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    window_title TEXT,
                    text_content TEXT,
                    source TEXT DEFAULT 'contextbridge_mac',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON context_events(timestamp)
            ''')
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_app_name ON context_events(app_name)
            ''')
    
    def store_context(self, context: Dict):
        """Store context event in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO context_events (timestamp, app_name, window_title, text_content, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                context['timestamp'],
                context['app_name'],
                context.get('window_title', ''),
                context['text_content'],
                context.get('source', 'contextbridge_mac')
            ))
    
    def get_recent_context(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent context events"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, app_name, window_title, text_content, source
                FROM context_events
                WHERE timestamp > datetime('now', '-{} hours')
                ORDER BY timestamp DESC
                LIMIT ?
            '''.format(hours), (limit,))
            
            return [
                {
                    'timestamp': row[0],
                    'app_name': row[1], 
                    'window_title': row[2],
                    'text_content': row[3],
                    'source': row[4]
                }
                for row in cursor.fetchall()
            ]
    
    def search_context(self, query: str, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Search context by text content"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, app_name, window_title, text_content, source
                FROM context_events  
                WHERE timestamp > datetime('now', '-{} hours')
                AND (text_content LIKE ? OR window_title LIKE ? OR app_name LIKE ?)
                ORDER BY timestamp DESC
                LIMIT ?
            '''.format(hours), (f'%{query}%', f'%{query}%', f'%{query}%', limit))
            
            return [
                {
                    'timestamp': row[0],
                    'app_name': row[1],
                    'window_title': row[2], 
                    'text_content': row[3],
                    'source': row[4]
                }
                for row in cursor.fetchall()
            ]
    
    def get_app_summary(self, hours: int = 8) -> Dict[str, int]:
        """Get summary of app usage"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT app_name, COUNT(*) as count
                FROM context_events
                WHERE timestamp > datetime('now', '-{} hours')
                GROUP BY app_name
                ORDER BY count DESC
            '''.format(hours))
            
            return {row[0]: row[1] for row in cursor.fetchall()}

class ContextBridgeMCPServer:
    def __init__(self, secret: str):
        self.secret = secret
        self.app = Flask(__name__)
        self.db = ContextDatabase()
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes for MCP server"""
        
        @self.app.route('/api/context', methods=['POST'])
        def receive_context():
            """Receive context data from ContextBridge Mac client"""
            try:
                context = request.get_json()
                if context:
                    self.db.store_context(context)
                    return {'status': 'ok'}
                return {'status': 'error', 'message': 'No data'}, 400
            except Exception as e:
                return {'status': 'error', 'message': str(e)}, 500
        
        @self.app.route('/mcp', methods=['POST'])
        def mcp_endpoint():
            """MCP protocol endpoint for OpenClaw"""
            # Verify secret
            auth_header = request.headers.get('X-ContextBridge-Secret')
            if auth_header != self.secret:
                return {'error': 'Unauthorized'}, 401
            
            try:
                mcp_request = request.get_json()
                method = mcp_request.get('method')
                params = mcp_request.get('params', {})
                
                if method == 'tools/list':
                    return {
                        'tools': [
                            {
                                'name': 'get_recent_context',
                                'description': 'Get recent screen context from the Mac',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'hours': {'type': 'number', 'description': 'Hours of history to retrieve', 'default': 4},
                                        'limit': {'type': 'number', 'description': 'Maximum number of events', 'default': 20}
                                    }
                                }
                            },
                            {
                                'name': 'search_context', 
                                'description': 'Search screen context by text content',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'query': {'type': 'string', 'description': 'Search query'},
                                        'hours': {'type': 'number', 'description': 'Hours of history to search', 'default': 8},
                                        'limit': {'type': 'number', 'description': 'Maximum results', 'default': 10}
                                    },
                                    'required': ['query']
                                }
                            },
                            {
                                'name': 'get_app_summary',
                                'description': 'Get summary of app usage from screen context', 
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {
                                        'hours': {'type': 'number', 'description': 'Hours to summarize', 'default': 8}
                                    }
                                }
                            },
                            {
                                'name': 'get_current_context',
                                'description': 'Get the most recent screen context',
                                'inputSchema': {
                                    'type': 'object',
                                    'properties': {}
                                }
                            }
                        ]
                    }
                
                elif method == 'tools/call':
                    tool_name = params.get('name')
                    arguments = params.get('arguments', {})
                    
                    if tool_name == 'get_recent_context':
                        hours = arguments.get('hours', 4)
                        limit = arguments.get('limit', 20)
                        contexts = self.db.get_recent_context(hours, limit)
                        return {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': f"Recent screen context ({len(contexts)} events from last {hours}h):\n\n" + 
                                           '\n'.join([
                                               f"[{ctx['timestamp'][:19]}] {ctx['app_name']}: {ctx['window_title'][:50]}{'...' if len(ctx['window_title']) > 50 else ''}\n  {ctx['text_content'][:150]}{'...' if len(ctx['text_content']) > 150 else ''}"
                                               for ctx in contexts
                                           ])
                                }
                            ]
                        }
                    
                    elif tool_name == 'search_context':
                        query = arguments.get('query', '')
                        hours = arguments.get('hours', 8)
                        limit = arguments.get('limit', 10)
                        results = self.db.search_context(query, hours, limit)
                        return {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': f"Context search for '{query}' ({len(results)} results):\n\n" +
                                           '\n'.join([
                                               f"[{ctx['timestamp'][:19]}] {ctx['app_name']}: {ctx['window_title'][:50]}{'...' if len(ctx['window_title']) > 50 else ''}\n  {ctx['text_content'][:200]}{'...' if len(ctx['text_content']) > 200 else ''}"
                                               for ctx in results
                                           ])
                                }
                            ]
                        }
                    
                    elif tool_name == 'get_app_summary':
                        hours = arguments.get('hours', 8)
                        summary = self.db.get_app_summary(hours)
                        return {
                            'content': [
                                {
                                    'type': 'text',
                                    'text': f"App usage summary (last {hours}h):\n\n" +
                                           '\n'.join([f"• {app}: {count} context events" for app, count in summary.items()])
                                }
                            ]
                        }
                    
                    elif tool_name == 'get_current_context':
                        recent = self.db.get_recent_context(hours=1, limit=1)
                        if recent:
                            ctx = recent[0]
                            return {
                                'content': [
                                    {
                                        'type': 'text',
                                        'text': f"Current context:\n[{ctx['timestamp'][:19]}] {ctx['app_name']}: {ctx['window_title']}\n\n{ctx['text_content']}"
                                    }
                                ]
                            }
                        else:
                            return {
                                'content': [
                                    {
                                        'type': 'text', 
                                        'text': "No recent context available"
                                    }
                                ]
                            }
                    
                    else:
                        return {'error': f'Unknown tool: {tool_name}'}, 400
                
                else:
                    return {'error': f'Unknown method: {method}'}, 400
                    
            except Exception as e:
                return {'error': str(e)}, 500
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return {'status': 'ok', 'events_stored': self.get_event_count()}
    
    def get_event_count(self) -> int:
        """Get total number of stored context events"""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute('SELECT COUNT(*) FROM context_events')
            return cursor.fetchone()[0]
    
    def run(self, host='0.0.0.0', port=8790):
        """Run the MCP server"""
        print(f"ContextBridge MCP Server starting on {host}:{port}")
        print(f"Context API endpoint: http://{host}:{port}/api/context")
        print(f"MCP endpoint: http://{host}:{port}/mcp")
        print(f"Health check: http://{host}:{port}/health")
        self.app.run(host=host, port=port, debug=False)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='ContextBridge MCP Server')
    parser.add_argument('--secret', default='yf28M-0xmlonP-zautzykrH9_wnEXLVGIGkqiOyStYM', help='API secret')
    parser.add_argument('--port', type=int, default=8790, help='Server port')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    
    args = parser.parse_args()
    
    server = ContextBridgeMCPServer(args.secret)
    server.run(host=args.host, port=args.port)

if __name__ == '__main__':
    main()