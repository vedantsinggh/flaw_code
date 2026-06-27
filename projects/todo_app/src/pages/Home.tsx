import { useEffect, useState } from 'react';
import { resourceApi } from '@/services/api';
import type { Resource } from '@/types';
import styles from './Home.module.css';

const Home = () => {
  const [resources, setResources] = useState<Resource[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchResources = async () => {
      try {
        const data = await resourceApi.getAll();
        setResources(data.data);
      } catch (err) {
        setError('Failed to fetch resources');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchResources();
  }, []);

  if (loading) return <div className={styles.status}>Loading...</div>;
  if (error) return <div className={styles.status}>{error}</div>;

  return (
    <div className={styles.container}>
      <h1>Resources</h1>
      <ul className={styles.list}>
        {resources.map((resource) => (
          <li key={resource.id} className={styles.item}>
            <h3>{resource.name}</h3>
            <p>{resource.description || 'No description provided.'}</p>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default Home;