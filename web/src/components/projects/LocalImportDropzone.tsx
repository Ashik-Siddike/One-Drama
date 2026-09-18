import React, { useState } from 'react'
import {
  UploadCloud,
  FolderOpen,
  FileVideo,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Loader2,
  ArrowRight,
  Archive,
  Copy,
  Move,
  X,
  RefreshCw,
} from 'lucide-react'
import type { LocalScanResult } from '../../types'
import { scanLocalPath, importLocalPath, uploadEpisodeFiles } from '../../services/api'

interface LocalImportDropzoneProps {
  onImportSuccess: () => Promise<void>
  onAutoProduce?: (opts: { query_or_url: string; limit?: number }) => Promise<void>
  onStartProcessing?: (opts?: any) => Promise<void>
  onClose?: () => void
  isModal?: boolean
}

export const LocalImportDropzone: React.FC<LocalImportDropzoneProps> = ({
  onImportSuccess,
  onAutoProduce,
  onStartProcessing,
  onClose,
  isModal = false,
}) => {
  const [activeTab, setActiveTab] = useState<'path' | 'direct'>('path')

  // Local Path Mode State
  const [localPathInput, setLocalPathInput] = useState('')
  const [isScanning, setIsScanning] = useState(false)
  const [scanResult, setScanResult] = useState<LocalScanResult | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)

  // Direct Drag & Drop Mode State
  const [droppedFiles, setDroppedFiles] = useState<File[]>([])
  const [isDraggingOver, setIsDraggingOver] = useState(false)

  // Ingest Config State
  const [archivePrevious, setArchivePrevious] = useState(true)
  const [renameToStandard, setRenameToStandard] = useState(true)
  const [copyOrMove, setCopyOrMove] = useState<'copy' | 'move'>('copy')

  // Ingestion Execution State
  const [isImporting, setIsImporting] = useState(false)
  const [importStatusMsg, setImportStatusMsg] = useState<string | null>(null)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  // -------------------------------------------------------------------------
  // Path Scan Handler
  // -------------------------------------------------------------------------
  const handleScanPath = async (pathToScan?: string) => {
    const target = (pathToScan || localPathInput).trim().replace(/^["']|["']$/g, '')
    if (!target) {
      setScanError('দয়া করে আপনার ড্রামা ফোল্ডার বা ফাইলের পাথ লিখুন বা পেস্ট করুন।')
      return
    }

    setIsScanning(true)
    setScanError(null)
    setScanResult(null)

    try {
      const res = await scanLocalPath(target)
      if (!res.valid || res.total_videos === 0) {
        setScanError(res.message || 'এই লোকেশনে কোনো ভিডিও ফাইল (.mp4, .mkv ইত্যাদি) পাওয়া যায়নি।')
      } else {
        setScanResult(res)
      }
    } catch (err: any) {
      setScanError(err.message || 'পাথ স্ক্যান করতে ব্যর্থ হয়েছে। নিশ্চিত করুন পাথটি সঠিক।')
    } finally {
      setIsScanning(false)
    }
  }

  // Handle Drag & Drop on Path Tab
  const handlePathDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDraggingOver(false)

    // Check for dropped plain text path
    const textData = e.dataTransfer.getData('text')
    if (textData && (textData.includes(':\\') || textData.includes(':/') || textData.startsWith('/'))) {
      const cleanPath = textData.trim().replace(/^["']|["']$/g, '')
      setLocalPathInput(cleanPath)
      handleScanPath(cleanPath)
      return
    }

    // Check for dropped files (if user dropped actual files onto the path dropzone)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files)
      // Check if browser exposed path (Electron/NW.js or some Windows browsers)
      const firstFile = files[0] as any
      if (firstFile.path) {
        const folderPath = firstFile.path.substring(0, Math.max(firstFile.path.lastIndexOf('\\'), firstFile.path.lastIndexOf('/')))
        if (folderPath) {
          setLocalPathInput(folderPath)
          handleScanPath(folderPath)
          return
        }
      }

      // Switch to direct file upload tab
      setActiveTab('direct')
      handleDirectFilesDrop(files)
    }
  }

  // -------------------------------------------------------------------------
  // Direct Drag & Drop Handlers
  // -------------------------------------------------------------------------
  const handleDirectFilesDrop = (files: File[]) => {
    const validVideoExts = ['.mp4', '.mkv', '.mov', '.flv', '.ts', '.webm', '.avi']
    const valid = files.filter((f) => {
      const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase()
      return validVideoExts.includes(ext) || f.type.startsWith('video/')
    })

    if (valid.length === 0) {
      setScanError('কোনো সমর্থিত ভিডিও ফাইল (.mp4, .mkv ইত্যাদি) পাওয়া যায়নি।')
      return
    }

    setDroppedFiles(valid)
    setScanError(null)
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleDirectFilesDrop(Array.from(e.target.files))
    }
  }

  // -------------------------------------------------------------------------
  // Ingest Execution
  // -------------------------------------------------------------------------
  const handleExecuteImport = async (startAutoPilot = false) => {
    setIsImporting(true)
    setImportStatusMsg('এপিসোডগুলো প্রজেক্টে ইনপোর্ট করা হচ্ছে...')

    try {
      if (activeTab === 'path') {
        if (!scanResult || scanResult.videos.length === 0) {
          throw new Error('প্রথমে একটি ফোল্ডার স্ক্যান করে ভিডিও কনফার্ম করুন।')
        }

        const res = await importLocalPath({
          path: scanResult.path,
          archive_previous: archivePrevious,
          copy_or_move: copyOrMove,
          rename_to_standard: renameToStandard,
        })

        setImportStatusMsg(`সফলভাবে ${res.imported_count}টি পর্ব ইনপোর্ট হয়েছে!`)
      } else {
        if (droppedFiles.length === 0) {
          throw new Error('দয়া করে অন্তত একটি ভিডিও ফাইল ড্রপ করুন।')
        }

        setUploadProgress(10)
        setImportStatusMsg(`${droppedFiles.length}টি পর্ব সরাসরি আপলোড হচ্ছে...`)
        const res = await uploadEpisodeFiles(droppedFiles, archivePrevious, renameToStandard)
        setUploadProgress(100)
        setImportStatusMsg(`সফলভাবে ${res.imported_count}টি পর্ব আপলোড হয়েছে!`)
      }

      await onImportSuccess()

      if (startAutoPilot) {
        setImportStatusMsg('🚀 সরাসরি হিন্দি ডাবিং ও ফুল মুভি রেন্ডার শুরু হচ্ছে...')
        if (onStartProcessing) {
          await onStartProcessing({ carry_context: true, generate_shorts: true })
        } else if (onAutoProduce) {
          await onAutoProduce({ query_or_url: 'local_imported_series', limit: 80 })
        }
      }

      setTimeout(() => {
        setIsImporting(false)
        if (onClose) onClose()
      }, 1200)
    } catch (err: any) {
      setScanError(`ইনপোর্ট ত্রুটি: ${err.message}`)
      setIsImporting(false)
    }
  }

  return (
    <div
      className={`rounded-2xl border transition-all ${
        isModal
          ? 'bg-zinc-950 border-zinc-700 shadow-2xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto'
          : 'bg-zinc-900/80 border-indigo-500/30 p-6 shadow-xl backdrop-blur-md'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-4 mb-5 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <UploadCloud className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <span>📥 লোকাল ড্রামা ও ভিডিও সিরিজ ইনপোর্ট</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Drag & Drop Ready
              </span>
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              বাইরে থেকে ডাউনলোড করা চাইনিজ ড্রামা ফোল্ডার বা ফাইল সরাসরি ড্র্যাগ-ড্রপ করে ওয়ান-ক্লিকে প্রোডাকশনে নিন।
            </p>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/80 transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Ingestion Mode Tabs */}
      <div className="flex gap-2 p-1 rounded-xl bg-zinc-950/80 border border-zinc-800 mb-5">
        <button
          type="button"
          onClick={() => setActiveTab('path')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'path'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
          }`}
        >
          <FolderOpen className="w-4 h-4" />
          <span>📁 ফোল্ডার বা পাথ ড্র্যাগ ও পেস্ট (আল্ট্রা-ফাস্ট লোকাল স্ক্যান)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('direct')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-xs font-semibold transition-all ${
            activeTab === 'direct'
              ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
          }`}
        >
          <FileVideo className="w-4 h-4" />
          <span>🎬 সরাসরি ভিডিও ফাইল ড্র্যাগ & ড্রপ (ব্রাউজার আপলোড)</span>
        </button>
      </div>

      {/* Tab 1: Local Path Ingestion */}
      {activeTab === 'path' && (
        <div className="space-y-4">
          {/* Dropzone Area for Local Path */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setIsDraggingOver(true)
            }}
            onDragLeave={() => setIsDraggingOver(false)}
            onDrop={handlePathDrop}
            className={`border-2 border-dashed rounded-2xl p-6 text-center transition-all cursor-pointer ${
              isDraggingOver
                ? 'border-indigo-400 bg-indigo-500/15 scale-[1.01]'
                : 'border-zinc-700/80 bg-zinc-950/50 hover:border-zinc-600 hover:bg-zinc-900/40'
            }`}
          >
            <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <FolderOpen className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-zinc-200 mb-1">
              উইন্ডোজ এক্সপ্লোরার থেকে ফোল্ডারটি এখানে টেনে এনে ছেড়ে দিন
            </h4>
            <p className="text-xs text-zinc-400 max-w-md mx-auto mb-4">
              অথবা আপনার কম্পিউটারের ড্রামা ফোল্ডারের পাথ (যেমন: <code className="text-indigo-300 font-mono">D:\Downloads\Drama_Ep1-80</code>) নিচের ঘরে পেস্ট করুন।
            </p>

            <div className="flex flex-col sm:flex-row gap-2 max-w-2xl mx-auto" onClick={(e) => e.stopPropagation()}>
              <input
                type="text"
                value={localPathInput}
                onChange={(e) => setLocalPathInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleScanPath()
                  }
                }}
                disabled={isScanning || isImporting}
                placeholder="পাথ পেস্ট করুন: E:\Downloads\Martial_Peak_Episodes"
                className="flex-1 px-4 py-2.5 rounded-xl bg-zinc-900 border border-zinc-700 text-xs text-zinc-100 font-mono placeholder-zinc-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              <button
                type="button"
                onClick={() => handleScanPath()}
                disabled={isScanning || isImporting || !localPathInput.trim()}
                className="flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs font-bold transition-all shadow-md shadow-indigo-600/20 shrink-0"
              >
                {isScanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>পাথ স্ক্যান করুন</span>
              </button>
            </div>
          </div>

          {/* Scan Results Preview */}
          {scanResult && (
            <div className="p-4 rounded-xl bg-zinc-950/90 border border-zinc-800 space-y-3 animate-fadeIn">
              <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-zinc-200">
                    {scanResult.total_videos}টি ভিডিও পর্ব সনাক্ত হয়েছে ({scanResult.total_size_mb} MB)
                  </span>
                </div>
                <span className="text-[10px] font-mono text-zinc-400 truncate max-w-xs">
                  {scanResult.path}
                </span>
              </div>

              {/* Episodes List Preview Table */}
              <div className="max-h-48 overflow-y-auto pr-1 space-y-1 font-mono text-xs">
                {scanResult.videos.map((vid, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 border border-zinc-800/80 text-[11px]"
                  >
                    <div className="flex items-center gap-2 truncate min-w-0">
                      <span className="text-zinc-500 text-[10px]">#{idx + 1}</span>
                      <span className="text-zinc-300 truncate">{vid.original_filename}</span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 text-zinc-400 text-[10px]">
                      <span>{vid.size_mb} MB</span>
                      {renameToStandard && (
                        <span className="flex items-center gap-1 text-indigo-400 font-bold bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                          <ArrowRight className="w-3 h-3" />
                          {vid.proposed_filename}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Direct Video Dropzone */}
      {activeTab === 'direct' && (
        <div className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setIsDraggingOver(true)
            }}
            onDragLeave={() => setIsDraggingOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setIsDraggingOver(false)
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleDirectFilesDrop(Array.from(e.dataTransfer.files))
              }
            }}
            className={`border-2 border-dashed rounded-2xl p-8 text-center transition-all cursor-pointer ${
              isDraggingOver
                ? 'border-indigo-400 bg-indigo-500/15 scale-[1.01]'
                : 'border-zinc-700/80 bg-zinc-950/50 hover:border-zinc-600 hover:bg-zinc-900/40'
            }`}
            onClick={() => document.getElementById('direct-file-input')?.click()}
          >
            <input
              id="direct-file-input"
              type="file"
              multiple
              accept="video/*,.mp4,.mkv,.mov,.flv,.ts,.webm"
              className="hidden"
              onChange={handleFileInputChange}
            />
            <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <FileVideo className="w-6 h-6" />
            </div>
            <h4 className="text-sm font-semibold text-zinc-200 mb-1">
              ভিডিও ফাইলগুলো এখানে ড্র্যাগ অ্যান্ড ড্রপ করুন
            </h4>
            <p className="text-xs text-zinc-400 max-w-md mx-auto mb-4">
              বা এখানে ক্লিক করে আপনার কম্পিউটার থেকে একসাথে একাধিক .mp4 / .mkv পর্ব নির্বাচন করুন।
            </p>
            <span className="inline-block px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold transition-all border border-zinc-700">
              📂 কম্পিউটার থেকে ভিডিও ফাইল সিলেক্ট করুন
            </span>
          </div>

          {/* Dropped Files Preview */}
          {droppedFiles.length > 0 && (
            <div className="p-4 rounded-xl bg-zinc-950/90 border border-zinc-800 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-zinc-200">
                    {droppedFiles.length}টি ফাইল নির্বাচিত হয়েছে (
                    {(droppedFiles.reduce((acc, f) => acc + f.size, 0) / (1024 * 1024)).toFixed(1)} MB)
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setDroppedFiles([])}
                  className="text-[11px] text-zinc-500 hover:text-red-400 font-mono"
                >
                  ক্লিয়ার করুন
                </button>
              </div>

              <div className="max-h-40 overflow-y-auto pr-1 space-y-1 font-mono text-xs">
                {droppedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg bg-zinc-900/60 border border-zinc-800/80 text-[11px]"
                  >
                    <span className="text-zinc-300 truncate max-w-sm">
                      #{idx + 1} {file.name}
                    </span>
                    <span className="text-zinc-500 text-[10px]">
                      {(file.size / (1024 * 1024)).toFixed(1)} MB
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {scanError && (
        <div className="flex items-center gap-2 p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{scanError}</span>
        </div>
      )}

      {/* Progress / Status Message */}
      {importStatusMsg && (
        <div className="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isImporting && <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />}
            <span>{importStatusMsg}</span>
          </div>
          {uploadProgress !== null && (
            <span className="font-mono font-bold text-xs">{uploadProgress}%</span>
          )}
        </div>
      )}

      {/* Ingestion Settings & Action Bar */}
      <div className="pt-4 border-t border-zinc-800 space-y-4">
        {/* Options Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <label className="flex items-center gap-2.5 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all">
            <input
              type="checkbox"
              checked={archivePrevious}
              onChange={(e) => setArchivePrevious(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 bg-zinc-900 border-zinc-700 w-4 h-4"
            />
            <div>
              <span className="font-semibold text-zinc-200 block">পূর্ববর্তী প্রজেক্ট আর্কাইভ</span>
              <span className="text-[10px] text-zinc-500">পুরনো পর্ব সংরক্ষণ করে ফ্রেশ শুরু</span>
            </div>
          </label>

          <label className="flex items-center gap-2.5 p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 cursor-pointer hover:border-zinc-700 transition-all">
            <input
              type="checkbox"
              checked={renameToStandard}
              onChange={(e) => setRenameToStandard(e.target.checked)}
              className="rounded text-indigo-600 focus:ring-indigo-500 bg-zinc-900 border-zinc-700 w-4 h-4"
            />
            <div>
              <span className="font-semibold text-zinc-200 block">স্ট্যান্ডার্ড নাম্বারিং</span>
              <span className="text-[10px] text-zinc-500">ep_001.mp4, ep_002.mp4...</span>
            </div>
          </label>

          {activeTab === 'path' ? (
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-zinc-950/60 border border-zinc-800">
              <span className="font-semibold text-zinc-300 text-xs">ফাইল মেথড:</span>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  onClick={() => setCopyOrMove('copy')}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all ${
                    copyOrMove === 'copy'
                      ? 'bg-indigo-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                  }`}
                  title="অরিজিনাল ফাইল অক্ষত রেখে কপি করে আনা হবে"
                >
                  <Copy className="w-3 h-3" />
                  <span>কপি</span>
                </button>
                <button
                  type="button"
                  onClick={() => setCopyOrMove('move')}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all ${
                    copyOrMove === 'move'
                      ? 'bg-amber-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                  }`}
                  title="তাৎক্ষণিক মুভ হবে (কোনো এক্সট্রা ডিস্ক স্পেস লাগবে না)"
                >
                  <Move className="w-3 h-3" />
                  <span>মুভ</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center p-3 rounded-xl bg-zinc-950/60 border border-zinc-800 text-[11px] text-zinc-400">
              <Archive className="w-4 h-4 mr-2 text-indigo-400" />
              <span>সরাসরি আপলোড মোড সক্রিয়</span>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 pt-3 border-t border-zinc-800">
          <div className="text-left">
            <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-200">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>
                {(activeTab === 'path' ? scanResult?.total_videos : droppedFiles.length) || 0}টি ভিডিও প্রস্তুত
              </span>
            </div>
            <span className="text-[11px] text-emerald-400 font-medium block">
              ✨ কোনো ডাউনলোডের দরকার নেই — সরাসরি আপনার এই ভিডিওগুলোই ডাবিং ও রেন্ডার হবে
            </span>
          </div>

          <div className="flex flex-col sm:flex-row gap-2.5 shrink-0">
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                disabled={isImporting}
                className="px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-semibold transition-all"
              >
                বাতিল
              </button>
            )}

            <button
              type="button"
              onClick={() => handleExecuteImport(false)}
              disabled={
                isImporting ||
                (activeTab === 'path' && (!scanResult || scanResult.total_videos === 0)) ||
                (activeTab === 'direct' && droppedFiles.length === 0)
              }
              title="ভিডিওগুলো শুধু ওয়ার্কস্পেসে সেভ হবে, ডাবিং এখনই শুরু হবে না"
              className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40 text-zinc-300 text-xs font-semibold transition-all border border-zinc-700"
            >
              {isImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <UploadCloud className="w-4 h-4 text-zinc-400" />}
              <span>📥 শুধু ইনপোর্ট (পরে রেন্ডার করবেন)</span>
            </button>

            <button
              type="button"
              onClick={() => handleExecuteImport(true)}
              disabled={
                isImporting ||
                (activeTab === 'path' && (!scanResult || scanResult.total_videos === 0)) ||
                (activeTab === 'direct' && droppedFiles.length === 0)
              }
              className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 hover:from-emerald-500 hover:to-indigo-500 disabled:opacity-40 text-white text-xs font-black tracking-wide transition-all shadow-lg shadow-emerald-600/30 transform hover:scale-[1.02]"
            >
              <Sparkles className="w-4 h-4 text-amber-300 animate-pulse" />
              <span>🎬 সরাসরি এই ভিডিওগুলো দিয়ে ফুল মুভি তৈরি শুরু করুন</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
