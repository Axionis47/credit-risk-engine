'use client'

import { useState, useRef } from 'react'
import { useHotkeys } from 'react-hotkeys-hook'
import { useMutation } from '@tanstack/react-query'
import { Copy, Loader2, Search, Wand2, ChevronDown, ChevronRight } from 'lucide-react'
import TextareaAutosize from 'react-textarea-autosize'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiClient } from '@/lib/api'
import { copyToClipboard, formatWordCount, getCoherenceColor, getCoherenceLabel } from '@/lib/utils'
import { ReferenceScript, ImprovedScript } from '@/types/api'

export function ScriptEditor() {
  const [draftBody, setDraftBody] = useState('')
  const [reference, setReference] = useState<ReferenceScript | null>(null)
  const [improvedScript, setImprovedScript] = useState<ImprovedScript | null>(null)
  const [isReferenceCollapsed, setIsReferenceCollapsed] = useState(false)
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null)

  const draftRef = useRef<HTMLTextAreaElement>(null)

  // Retrieve reference mutation
  const retrieveMutation = useMutation({
    mutationFn: (body: string) => apiClient.retrieveReference(body),
    onSuccess: (response) => {
      if (response.success && response.data?.ref) {
        setReference(response.data.ref)
      } else {
        setReference(null)
        // Show reason if no reference found
        if (response.data?.reason) {
          alert(`No reference found: ${response.data.reason}`)
        }
      }
    },
    onError: (error) => {
      console.error('Retrieve failed:', error)
      alert('Failed to retrieve reference. Please try again.')
    }
  })

  // Improve script mutation
  const improveMutation = useMutation({
    mutationFn: ({ body, ref }: { body: string; ref?: ReferenceScript }) => 
      apiClient.improveScript(body, ref),
    onSuccess: (response) => {
      if (response.success && response.data?.result) {
        setImprovedScript(response.data.result)
        
        // Show warnings if any
        if (response.data.warnings?.length > 0) {
          console.warn('Improvement warnings:', response.data.warnings)
        }
      }
    },
    onError: (error) => {
      console.error('Improve failed:', error)
      alert('Failed to improve script. Please try again.')
    }
  })

  // Keyboard shortcuts
  useHotkeys('ctrl+enter,cmd+enter', () => handleImprove(), { enableOnFormTags: true })
  useHotkeys('ctrl+k,cmd+k', () => handleRetrieve(), { enableOnFormTags: true })
  useHotkeys('ctrl+shift+c,cmd+shift+c', () => handleCopyAll(), { enableOnFormTags: true })

  const handleRetrieve = () => {
    if (!draftBody.trim()) {
      alert('Please enter a draft script first')
      return
    }
    retrieveMutation.mutate(draftBody)
  }

  const handleImprove = () => {
    if (!draftBody.trim()) {
      alert('Please enter a draft script first')
      return
    }
    improveMutation.mutate({ body: draftBody, ref: reference || undefined })
  }

  const handleCopy = async (text: string, label: string) => {
    try {
      await copyToClipboard(text)
      setCopyFeedback(`${label} copied!`)
      setTimeout(() => setCopyFeedback(null), 2000)
    } catch (error) {
      console.error('Copy failed:', error)
      alert('Failed to copy to clipboard')
    }
  }

  const handleCopyAll = () => {
    if (!improvedScript) return
    
    const allText = `Title: ${improvedScript.title}\n\nHook: ${improvedScript.hook}\n\nBody: ${improvedScript.body}`
    handleCopy(allText, 'All content')
  }

  return (
    <div className="h-screen flex">
      {/* Left Pane - Draft Input */}
      <div className="w-1/2 flex flex-col border-r">
        <div className="p-4 border-b bg-muted/50">
          <h2 className="text-lg font-semibold mb-4">Draft Script</h2>
          <div className="flex gap-2">
            <Button
              onClick={handleRetrieve}
              disabled={!draftBody.trim() || retrieveMutation.isPending}
              variant="outline"
              size="sm"
            >
              {retrieveMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Search className="w-4 h-4 mr-2" />
              )}
              Retrieve REF
              <kbd className="ml-2 px-1.5 py-0.5 text-xs bg-muted rounded">⌘K</kbd>
            </Button>
            <Button
              onClick={handleImprove}
              disabled={!draftBody.trim() || improveMutation.isPending}
              size="sm"
            >
              {improveMutation.isPending ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Wand2 className="w-4 h-4 mr-2" />
              )}
              Improve
              <kbd className="ml-2 px-1.5 py-0.5 text-xs bg-muted rounded">⌘↵</kbd>
            </Button>
          </div>
        </div>
        
        <div className="flex-1 p-4">
          <TextareaAutosize
            ref={draftRef}
            value={draftBody}
            onChange={(e) => setDraftBody(e.target.value)}
            placeholder="Paste your draft script here..."
            className="w-full h-full resize-none border-0 outline-none text-sm leading-relaxed custom-scrollbar"
            minRows={20}
          />
        </div>
        
        <div className="p-4 border-t bg-muted/50 text-sm text-muted-foreground">
          Words: {formatWordCount(draftBody.split(/\s+/).filter(Boolean).length)}
        </div>
      </div>

      {/* Right Pane - Reference + Output */}
      <div className="w-1/2 flex flex-col">
        {/* Reference Section */}
        {reference && (
          <div className={`border-b transition-all duration-200 ${isReferenceCollapsed ? 'h-12' : 'h-1/3'}`}>
            <div className="p-4 bg-blue-50 border-b flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsReferenceCollapsed(!isReferenceCollapsed)}
                  className="p-1 h-6 w-6"
                >
                  {isReferenceCollapsed ? (
                    <ChevronRight className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </Button>
                <h3 className="font-medium">Reference Script</h3>
                <Badge variant="outline" className="text-xs">
                  {formatWordCount(reference.performance.views)} views
                </Badge>
                {reference.performance.ctr && (
                  <Badge variant="outline" className="text-xs">
                    {(reference.performance.ctr * 100).toFixed(1)}% CTR
                  </Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleCopy(reference.body, 'Reference')}
                className="h-6 px-2"
              >
                <Copy className="w-3 h-3" />
              </Button>
            </div>
            
            {!isReferenceCollapsed && (
              <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
                <pre className="text-sm leading-relaxed whitespace-pre-wrap">
                  {reference.body}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Output Section */}
        <div className="flex-1 flex flex-col">
          <div className="p-4 border-b bg-muted/50">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Improved Script</h3>
              {improvedScript && (
                <div className="flex items-center gap-2">
                  {/* Coherence Pill */}
                  <div className="flex items-center gap-1">
                    <div className={`w-2 h-2 rounded-full ${getCoherenceColor(improvedScript.coherence.score)}`} />
                    <span className="text-xs font-medium">
                      {getCoherenceLabel(improvedScript.coherence.score, improvedScript.coherence.passed)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({(improvedScript.coherence.score * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopyAll}
                    className="h-6 px-2"
                  >
                    <Copy className="w-3 h-3 mr-1" />
                    Copy All
                    <kbd className="ml-1 px-1 py-0.5 text-xs bg-muted rounded">⌘⇧C</kbd>
                  </Button>
                </div>
              )}
            </div>
          </div>

          {improvedScript ? (
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              {/* Title */}
              <div className="p-4 border-b">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Title</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCopy(improvedScript.title, 'Title')}
                    className="h-6 px-2"
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                <p className="text-sm font-medium">{improvedScript.title}</p>
              </div>

              {/* Hook */}
              <div className="p-4 border-b">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Hook</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCopy(improvedScript.hook, 'Hook')}
                    className="h-6 px-2"
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                <p className="text-sm leading-relaxed">{improvedScript.hook}</p>
              </div>

              {/* Body */}
              <div className="p-4 border-b">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Body</h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleCopy(improvedScript.body, 'Body')}
                    className="h-6 px-2"
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
                <pre className="text-sm leading-relaxed whitespace-pre-wrap">
                  {improvedScript.body}
                </pre>
              </div>

              {/* Stats */}
              <div className="p-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-4">
                  <span>Words: {formatWordCount(improvedScript.word_count)}</span>
                  {improvedScript.coherence.notes && (
                    <span>Note: {improvedScript.coherence.notes}</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <Wand2 className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Enter a draft script and click "Improve" to get started</p>
                <p className="text-xs mt-2">Use ⌘K to retrieve a reference first</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Copy Feedback */}
      {copyFeedback && (
        <div className="fixed bottom-4 right-4 bg-green-600 text-white px-3 py-2 rounded-md text-sm">
          {copyFeedback}
        </div>
      )}
    </div>
  )
}
