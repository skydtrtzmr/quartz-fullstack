export const layoutData = {
  explorer: {
    sort: {
      type: 'natural',
      order: 'asc',
      field: '',
    },
  },
  folderPage: {
    sort: {
      type: 'natural',
      order: 'asc',
      field: '',
    },
  },
  backlinks: {
    hideWhenEmpty: false,
    aggregation: [
      {
        type: 'folder',
        depth: 1,
      },
      {
        type: 'field',
        field: 'type',
      },
      {
        type: 'date',
        field: 'date',
        granularity: 'year',
      },
    ],
  },
  graph: {
    coreNodeFilter: [
      {
        type: 'folder',
        depth: 1,
        values: ['项目'],
      },
    ],
    coreNodeLimit: 50,
    regionRules: [
      {
        type: 'field',
        field: 'type',
      },
    ],
    aggregation: [
      {
        type: 'folder',
        depth: 1,
      },
      {
        type: 'field',
        field: 'type',
      },
      {
        type: 'date',
        field: 'date',
        granularity: 'year',
      },
    ],
  },
}
