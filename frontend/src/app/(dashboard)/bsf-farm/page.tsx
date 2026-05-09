'use client'

import { Leaf, FlaskConical, ArrowRight } from 'lucide-react'

export default function BSFFarmPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">BSF Farm</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Black Soldier Fly bioconversion tracking
        </p>
      </div>

      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center mb-5">
          <Leaf className="w-8 h-8 text-emerald-500" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Coming Soon</h2>
        <p className="text-sm text-gray-500 max-w-sm leading-relaxed">
          BSF bioconversion tracking will be available once the farm operation is active.
          This module will track food waste intake, larvae conversion ratios, and protein output.
        </p>
        <div className="mt-8 flex flex-col gap-3 text-left max-w-xs w-full">
          {[
            'Food waste intake from collection jobs',
            'Larvae batch tracking & conversion ratios',
            'Protein output and livestock recipient records',
            'Circularity metrics for ESG reporting',
          ].map((item) => (
            <div key={item} className="flex items-start gap-2.5 text-sm text-gray-500">
              <FlaskConical className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
