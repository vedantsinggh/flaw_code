import React from 'react';
import { useTodos, FilterType } from '../../context/TodoContext';
import styles from './FilterBar.module.css';

const FilterBar: React.FC = () => {
  const { filter, setFilter, searchQuery, setSearchQuery } = useTodos();

  const filters: { label: string; value: FilterType }[] = [
    { label: 'All', value: 'all' },
    { label: 'Active', value: 'active' },
    { label: 'Completed', value: 'completed' },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.searchContainer}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search tasks..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>
      <div className={styles.filters}>
        {filters.map((f) => (
          <button
            key={f.value}
            className={`${styles.filterButton} ${filter === f.value ? styles.active : ''}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default FilterBar;