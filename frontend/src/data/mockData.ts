export type QualityIssue = 'overexposed' | 'underexposed' | 'blurry'

export interface MockPhoto {
  id: string
  fileName: string
  resolution: string
  issues: QualityIssue[]
  liked: boolean
  dateAdded: string
  url: string
  size: string
}

export interface StagedFile {
  id: string
  fileName: string
  size: string
  thumbnail: string
}

export const ISSUE_META: Record<QualityIssue, { label: string; color: string; bgColor: string; borderColor: string; icon: string }> = {
  overexposed: {
    label: 'Over-exposed',
    color: 'text-amber-300',
    bgColor: 'bg-amber-400/[0.08]',
    borderColor: 'border-amber-400/20',
    icon: '☀️',
  },
  underexposed: {
    label: 'Under-exposed',
    color: 'text-blue-300',
    bgColor: 'bg-blue-400/[0.08]',
    borderColor: 'border-blue-400/20',
    icon: '🌙',
  },
  blurry: {
    label: 'Blurry',
    color: 'text-rose-300',
    bgColor: 'bg-rose-400/[0.08]',
    borderColor: 'border-rose-400/20',
    icon: '◎',
  },
}

export const MOCK_PHOTOS: MockPhoto[] = [
  {
    id: '1',
    fileName: 'DSC_0421.jpg',
    resolution: '6000 × 4000',
    issues: [],
    liked: true,
    dateAdded: '2026-10-28',
    url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=600&h=400&fit=crop',
    size: '12.4 MB',
  },
  {
    id: '2',
    fileName: 'IMG_1087.png',
    resolution: '4032 × 3024',
    issues: ['overexposed'],
    liked: false,
    dateAdded: '2026-10-27',
    url: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=600&h=400&fit=crop',
    size: '8.1 MB',
  },
  {
    id: '3',
    fileName: 'DSCF_2200.jpg',
    resolution: '5472 × 3648',
    issues: ['blurry'],
    liked: false,
    dateAdded: '2026-10-26',
    url: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=600&h=400&fit=crop',
    size: '14.7 MB',
  },
  {
    id: '4',
    fileName: 'A7R_0033.jpg',
    resolution: '7952 × 5304',
    issues: ['underexposed'],
    liked: false,
    dateAdded: '2026-10-25',
    url: 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=600&h=400&fit=crop',
    size: '22.3 MB',
  },
  {
    id: '5',
    fileName: 'P1000587.jpg',
    resolution: '4592 × 3448',
    issues: [],
    liked: true,
    dateAdded: '2026-10-24',
    url: 'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?w=600&h=400&fit=crop',
    size: '9.8 MB',
  },
  {
    id: '6',
    fileName: 'R0001445.jpg',
    resolution: '6000 × 4000',
    issues: ['overexposed', 'blurry'],
    liked: false,
    dateAdded: '2026-10-23',
    url: 'https://images.unsplash.com/photo-1472214103451-9374bd1c798e?w=600&h=400&fit=crop',
    size: '11.2 MB',
  },
  {
    id: '7',
    fileName: 'IMG_4402.jpg',
    resolution: '4032 × 3024',
    issues: [],
    liked: true,
    dateAdded: '2026-10-22',
    url: 'https://images.unsplash.com/photo-1465146344425-f00d5f5c8f07?w=600&h=400&fit=crop',
    size: '7.6 MB',
  },
  {
    id: '8',
    fileName: 'DSC_0899.jpg',
    resolution: '6016 × 4016',
    issues: ['underexposed', 'blurry'],
    liked: false,
    dateAdded: '2026-10-21',
    url: 'https://images.unsplash.com/photo-1518173946687-a1e359b014ce?w=600&h=400&fit=crop',
    size: '15.9 MB',
  },
  {
    id: '9',
    fileName: 'FUJI_0122.jpg',
    resolution: '6240 × 4160',
    issues: ['blurry'],
    liked: false,
    dateAdded: '2026-10-20',
    url: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&h=400&fit=crop',
    size: '18.3 MB',
  },
  {
    id: '10',
    fileName: 'SONY_7811.jpg',
    resolution: '7952 × 5304',
    issues: ['overexposed'],
    liked: false,
    dateAdded: '2026-10-19',
    url: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=600&h=400&fit=crop',
    size: '24.1 MB',
  },
]

export const MOCK_STAGED_FILES: StagedFile[] = [
  {
    id: 's1',
    fileName: 'vacation_001.jpg',
    size: '4.2 MB',
    thumbnail: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=80&h=80&fit=crop',
  },
  {
    id: 's2',
    fileName: 'portrait_final.png',
    size: '8.7 MB',
    thumbnail: 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=80&h=80&fit=crop',
  },
  {
    id: 's3',
    fileName: 'sunset_raw.CR2',
    size: '25.1 MB',
    thumbnail: 'https://images.unsplash.com/photo-1495616811223-4d98c6e9c869?w=80&h=80&fit=crop',
  },
]
