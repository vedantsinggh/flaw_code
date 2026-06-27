import React, { useState, FormEvent } from 'react';
import { useTodos } from '../../context/TodoContext';
import styles from './TodoForm.module.css';

const TodoForm: React.FC = () => {
  const [text, setText] = useState('');
  const { addTodo } = useTodos();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    await addTodo(text);
    setText('');
  };

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <input
        type="text"
        className={styles.input}
        placeholder="What needs to be done?"
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoFocus
      />
      <button type="submit" className={styles.button} disabled={!text.trim()}>
        Add Task
      </button>
    </form>
  );
};

export default TodoForm;